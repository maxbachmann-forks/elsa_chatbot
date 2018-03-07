#!/usr/bin/env python
import torch, sys
import torch.nn.functional as F
import torch.nn as nn
import torch.autograd as autograd
from .sentence_encoder import Sentence_Encoder
from .model_base import Model_Base

class Dialog_Tracker(Model_Base):
    def __init__(self, cfg, vocab, Nresponses):
        super().__init__(cfg, vocab)
        self.Nresponses = Nresponses
        self.network()

    def network(self):
        self.encoder = Sentence_Encoder(self.cfg, self.vocab)
        self.encoder.network()
        self.conv = nn.Conv2d(in_channels = 1, \
                out_channels = self.cfg['cnn_kernel_num'], \
                kernel_size = (self.cfg['cnn_kernel_size'], self.vocab.emb_ins.vec_len),\
                padding = 0)
        self.dropout = nn.Dropout(self.cfg['dropout'])
        self.pool = nn.AvgPool1d(2)
        self.fc_entity1 = nn.Linear(self.cfg['max_entity_types'],self.cfg['max_entity_types'])
        self.fc_entity2 = nn.Linear(self.cfg['max_entity_types'],self.cfg['max_entity_types'])
        self.fc_response1 = nn.Linear(self.Nresponses, self.cfg['fc_response1'])
        self.fc_response2 = nn.Linear(self.cfg['fc_response1'], self.cfg['fc_response2'])
        fc1_input_size = self.cfg['cnn_kernel_num']*2 + self.cfg['max_entity_types'] + self.cfg['fc_response2']
        self.fc_dialog = nn.Linear(fc1_input_size, self.cfg['dialog_emb_size'])
        self.lstm = nn.LSTM(self.cfg['dialog_emb_size'], self.Nresponses)
        self.softmax = nn.Softmax(dim=1)
        self.lstm_hidden = self.init_hidden()

    def entityencoder(self, x):
        x = self.fc_entity1(x)
        x = self.fc_entity2(x)
        x = self.dropout(x)
        return x

    def responseencoder(self, x):
        x = self.fc_response1(x)
        x = self.fc_response2(x)
        x = self.dropout(x)
        return x

    def init_hidden(self):
        return (autograd.Variable(torch.zeros(1, 1, self.Nresponses)),
                autograd.Variable(torch.zeros(1, 1, self.Nresponses)))
        

    def dialog_embedding(self, utterance, entity,  response_prev):
        #utterance embedding
        utterance = self.encoder(utterance) 
        utter_att = self.attention(utterance, utterance) 
        #entity name embedding
        entity = self.entityencoder(entity) 
        #previous response embedding
        response_prev = self.responseencoder(response_prev)
        #concat together and apply linear
        utter = torch.cat((utter_att, entity, response_prev), 1)
        utter = self.fc_dialog(utter) 
        return self.softmax(utter)

    def get_response(dialog):
        #first get dialog embedding
        dialog_emb = self.dialog_embedding(d['utterance'], d['entity'], d['response_prev'])
        #dialog embedding to lstm as dialog tracker
        lstm_out, _ = self.lstm(dialog_emb.view(len(dialog_emb),1,-1), self.lstm_hidden)
        lstm_out = lstm_out.view(len(dialog_emb), -1)
        #output to softmax
        lstm_softmax = self.softmax(lstm_out)
        response = lstm_softmax * d['mask']
        response = torch.log(response + 1e-15)
    

    def forward(self, dialogs):
        responses = []
        for d in dialogs:
            responses.append(self.get_response(d))
        #concat all dialogs output together
        responses = torch.cat(responses, 0)
        return responses

