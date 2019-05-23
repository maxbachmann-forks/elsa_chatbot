#!/usr/bin/env python
import torch
import torch.nn as nn
from torch.nn.utils.rnn import PackedSequence
from .sentence_encoder import SentenceEncoder

'''
    Author: Pengjia Zhu (zhupengjia@gmail.com)
'''

class DialogTracker(nn.Module):
    '''
        dialog tracker for end2end chatbot 

        Input:
            - skill_name: string, current skill name
            - encoder: sentence encoder instance from .sentence_encoder
            - Nresponses: number of available responses
            - kernel_num: int
            - kernel_size: int
            - max_entity_types: int
            - fc_responses: int for int list, default is 5
            - entity_layers: int, default is 2
            - num_hidden_layers: int, default is 1
            - dropout: float, default is 0.2
            
    '''
    def __init__(self, skill_name, num_responses, max_entity_types, shared_layers=None,
                 model_type="transformer", bert_model_name=None, vocab_size=30522,
                 encoder_hidden_layers=12, encoder_attention_heads=12, max_position_embeddings=512,
                 encoder_intermediate_size=1024, encoder_hidden_size=768,
                 entity_layers=2, entity_emb_dim=50, num_hidden_layers=1, hidden_size=300,
                 dropout=0, **args):
        super().__init__()
        if shared_layers is None or not "encoder" in shared_layers:
            self.encoder = SentenceEncoder(bert_model_name=bert_model_name,
                                           model_type=model_type,
                                           vocab_size=vocab_size,
                                           encoder_hidden_layers= encoder_hidden_layers,
                                           encoder_attention_heads=encoder_attention_heads,
                                           max_position_embeddings=max_position_embeddings,
                                           encoder_intermediate_size=encoder_intermediate_size,
                                           encoder_hidden_size=encoder_hidden_size,
                                           dropout=dropout)
            if shared_layers is not None:
                shared_layers["encoder"] = self.encoder
        else:
            self.encoder = shared_layers["encoder"]
        
        self.config = {"encoder":self.encoder.config,
                       "decoder":{
                           "num_responses": num_responses,
                           "entity_layers": entity_layers,
                           "entity_emb_dim": entity_emb_dim,
                           "num_hidden_layers": num_hidden_layers,
                           "hidden_size": hidden_size}
                      }

        encoder_hidden_size = self.config["encoder"]["hidden_size"]
        
        self.response_key = 'response_' + skill_name
        self.mask_key = 'response_mask_' + skill_name

        self.dropout = nn.Dropout(dropout)
        self.pool = nn.AvgPool1d(2)

        fc_entity_layers = [nn.Linear(max_entity_types, max_entity_types) for i in range(entity_layers-1)]
        fc_entity_layers.append(nn.Linear(max_entity_types, entity_emb_dim))
        self.fc_entity = nn.Sequential(*fc_entity_layers)

        self.fc_dialog = nn.Linear(encoder_hidden_size+ entity_emb_dim, hidden_size)
        
        self.lstm = nn.LSTM(hidden_size, hidden_size, num_layers=num_hidden_layers, batch_first=True)
        self.fc_out = nn.Linear(hidden_size, num_responses)
        self.loss_function = nn.NLLLoss()
        self.softmax = nn.LogSoftmax(dim=1) if self.training else nn.Softmax(dim=1)

    def entityencoder(self, x):
        '''
            entity encoder, model framwork:
                - linear + linear 

            Input:
                - onehot present of entity names
        '''
        x = self.fc_entity(x)
        x = self.dropout(x)
        return x

    
    def dialog_embedding(self, utterance, utterance_mask, entity):
        '''
            Model framework:
                - utterance_embedding + entityname_embedding + prev_response embedding -> linear

            Get dialog embedding from utterance, entity, response_prev

            Input:
                - utterance, entity, response_prev are from three related keys of dialog_status.torch output

            Output:
                - dialog embedding
        '''
        #utterance embedding
        sequence_output, pooled_output = self.encoder(utterance, attention_mask=utterance_mask, output_all_encoded_layers=False)

        #entity name embedding
        entity = self.entityencoder(entity) 
       
        #concat together and apply linear
        utter = torch.cat((pooled_output, entity), 1)
        
        emb = self.fc_dialog(utter)
        
        return emb


    def forward(self, dialogs):
        '''
            Model framework:
                - dialogs -> dialog_embedding -> lstm -> softmax*mask -> logsoftmax
            
            Input:
                - dialogs: output from dialog_status.torch
            
            output:
                - logsoftmax
        '''
        #first get dialog embedding
        pack_batch = dialogs['utterance'].batch_sizes

        dialog_emb = self.dialog_embedding(dialogs['utterance'].data, dialogs["utterance_mask"].data, dialogs['entity'].data)

        dialog_emb = PackedSequence(dialog_emb, pack_batch) #feed batch_size and pack to packedsequence
        
        #dialog embedding to lstm as dialog tracker

        lstm_out, (ht, ct) = self.lstm(dialog_emb)
        
        lstm_out = self.dropout(lstm_out.data)

        hidden = self.fc_out(lstm_out)

        if self.training and self.response_key in dialogs:
            y_prob = self.softmax(hidden)
            y_true = dialogs[self.response_key].data
            loss = self.loss_function(y_prob, y_true.squeeze(1))
            return y_prob, loss

        #output to softmax
        lstm_softmax = self.softmax(hidden)

        #apply mask 
        response = lstm_softmax * dialogs[self.mask_key].data + 1e-15
        y_prob = torch.log(response)

        return y_prob


