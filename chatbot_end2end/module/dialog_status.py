#!/usr/bin/env python
"""
    Author: Pengjia Zhu (zhupengjia@gmail.com)
"""
import copy
import numpy
import torch
from torch.nn import functional as F
from torch.nn.utils.rnn import pack_padded_sequence
from .entity_dict import EntityDict
from .dialog_data import DialogData


def dialog_collate(batch):
    """
        Collate function for torch.data.generator
    """
    if not batch:
        return []
    data = DialogData({})
    dialog_lengths = numpy.array([b["utterance"].shape[0]
                                  for b in batch], "int")
    perm_idx = dialog_lengths.argsort()[::-1].astype("int")
    dialog_lengths = dialog_lengths[perm_idx]
    max_dialog_len = int(dialog_lengths[0])

    for k in batch[0].keys():
        # padding
        for b in batch:
            padshape = [0]*(b[k].dim()*2)
            padshape[-1] = int(max_dialog_len - b[k].shape[0])
            b[k] = F.pad(b[k], padshape)
        # stack
        data[k] = torch.stack([b[k] for b in batch])
        # pack
        data[k] = pack_padded_sequence(data[k][perm_idx], dialog_lengths,
                                       batch_first=True)

    return data


def format_sentence(vocab, token_ids, max_seq_len):
    """
        Format token ids to sentence and masks

        Input:
            - vocab:  instance of nlptools.text.vocab
            - token_ids: list of token ids
            - max_seq_len: int
    """
    token_ids = token_ids[:self.max_seq_len-2]
    seq_len = len(token_ids) + 2
    sentence = numpy.zeros(max_seq_len, 'int')
    sentence_mask = numpy.zeros(max_seq_len, 'int')
    sentence[0] = vocab.BOS_ID
    sentence[1:seq_len-1] = token_ids
    sentence[seq_len-1] = vocab.EOS_ID
    sentence_mask[:seq_len] = 1
    return sentence, sentence_mask


class DialogStatus:
    def __init__(self, vocab, tokenizer, ner, topic_manager,
                 sentiment_analyzer, max_seq_len=100,
                 max_entity_types=1024, rl_maxloop=20, rl_discount=0.95):
        """
        Maintain the dialog status in a dialog

        The dialog status will maintain:
            - utterance history
            - response history
            - entity mask history
            - entity history
            - current entity mask
            - current entities

        The class also provide the method to convert those data
        to torch variables

        To use this class, one must do the following steps:
            - add_utterance: add the current utterance to status,
                the entities will be extracted from utterance
            - update_response/get_response: updated the current
                response to status or get response from current_status

        Input:
            - vocab:  instance of nlptools.text.vocab
            - tokenizer:  instance of nlptools.text.Tokenizer
            - ner: instance of nlptools.text.ner
            - topic_manager: topic manager instance,
                see src/module/topic_manager
            - sentiment_analyzer: sentiment analyzer instance
            - max_seq_len: int, maximum sequence length
            - max_entity_types: int, maximum entity types

        Special usage:
            - str(): print the current status
            - len(): length of dialog

        """

        self.tokenizer = tokenizer
        self.ner = ner
        self.vocab = vocab
        self.topic_manager = topic_manager
        self.max_seq_len = max_seq_len
        self.max_entity_types = max_entity_types
        self.rl_maxloop = rl_maxloop
        self.rl_discount = rl_discount

        self.current_status = self.__init_status()

        self.history_status = []
        self.sentiment_analyzer = sentiment_analyzer

    def __init_status(self):
        initstatus = {"entity": {},
                      "entity_emb": None,
                      "utterance": None,
                      "utterance_mask": None,
                      "response_string": None,
                      "sentiment": 0,
                      "topic": None
                      }
        return initstatus

    @classmethod
    def new_dialog(cls, vocab, tokenizer, ner, topic_manager,
                   sentiment_analyzer, max_seq_len=100,
                   max_entity_types=1024):
        """
            create a new dialog
            data[k][tk] = data[k][tk].data
        """
        return cls(vocab, tokenizer, ner, topic_manager,
                   sentiment_analyzer, max_seq_len, max_entity_types)

    def add_utterance(self, utterance):
        """
            add utterance to status

            Input:
                - utterance: string

            Output:
                - if success, return True, otherwise return None

        """
        # get entities
        utterance = utterance.strip()
        entities, utterance_replaced = self.ner.get(utterance,
                                                    return_dict=True)
        for e in entities:
            # only keep first value
            self.current_status["entity"][e] = entities[e][0]
        self.current_status["entity_emb"] =\
            EntityDict.name2onehot(self.current_status["entity"].keys(),
                                   self.max_entity_types).astype("float32")

        # utterance to id
        tokens = self.tokenizer(utterance_replaced)
        utterance_ids = self.vocab.words2id(tokens)

        self.current_status["utterance"], self.current_status["utterance_mask"] =\
                format_sentence(self.vocab, utterance_ids, self.max_seq_len)

        # get topic
        self.current_status["topic"] = self.topic_manager.get_topic(
            self.current_status)

        # get sentiment
        self.current_status["sentiment"] = self.sentiment_analyzer(utterance)

        # response mask
        self.current_status = self.topic_manager.update_response_masks(
            self.current_status)

    def add_response(self, response):
        """
            add existed response, usually for training data

            Input:
                - response: string
        """
        response = response.strip()
        entities, response_replaced = self.ner.get(response, return_dict=True)

        self.current_status = \
            self.topic_manager.add_response(response_replaced,
                                            self.current_status)
        self.history_status.append(copy.deepcopy(self.current_status))

    def get_response(self, device):
        """
            get response from current status

            Input:
                - device: torch device
        """
        current_data = self.status2data()
        current_data.to(device)
        self.current_status = \
            self.topic_manager.get_response(current_data,
                                            self.current_status)
        self.history_status.append(copy.deepcopy(self.current_status))
        return self.current_status['response_string']

    def __str__(self):
        """
            print the current status
        """
        txt = '='*60 + '\n'
        for k in self.current_status:
            txt += "{}: {}\n".format(k, str(self.current_status[k]))
        return txt

    def __len__(self):
        """
            length of dialog
        """
        return len(self.history_status)

    def data(self, topic_names=None, status_list=None,
             turn_start=0):
        """
            return pytorch data for all messages in this dialog

            Input:
                - topic_names: list of topic name need to return,
                    default is None to return all available topics
                - status_list: list status need to predeal,
                    default is None for history status
                - turn_start: int, which turn loop for first status,
                    default is 0
        """
        if status_list is None:
            status_list = self.history_status
        n_status = len(status_list)
        status = {"entity": numpy.zeros((n_status, self.max_entity_types),
                                        'float32'),
                  "utterance": numpy.zeros((n_status, self.max_seq_len),
                                           'int'),
                  "utterance_mask": numpy.zeros((n_status, self.max_seq_len),
                                                'int'),
                  "reward": numpy.zeros((n_status, 1), 'float32'),
                  "sentiment": numpy.zeros((n_status, 1), 'float32')
                  }

        if topic_names is None:
            topic_names = self.topic_manager.topics.keys()

        if n_status+turn_start < self.rl_maxloop:
            reward_base = 1
        else:
            reward_base = 0

        for i, s in enumerate(status_list):
            status["entity"][i] = s["entity_emb"]
            status["utterance"][i] = s["utterance"]
            status["utterance_mask"][i] = s["utterance_mask"]
            status["sentiment"][i, 0] = s["sentiment"]
            status["reward"][i, 0] =\
                reward_base * self.rl_discount**(i+turn_start)
            for tk in topic_names:
                for k in ["response", "response_mask"]:
                    rkey = k+'_'+tk
                    if rkey not in s:
                        continue
                    if rkey not in status:
                        if isinstance(s[rkey], numpy.ndarray):
                            status[rkey] = numpy.repeat(
                                numpy.expand_dims(
                                    numpy.zeros_like(s[rkey]), axis=0),
                                n_status, axis=0)
                        else:
                            status[rkey] = numpy.zeros((n_status, 1),
                                                       type(s[rkey]))
                    status[rkey][i] = s[rkey]
        status["reward"] = status["reward"]/(n_status+turn_start)

        return status

    def status2data(self, topic_names=None, status=None):
        """
            convert to pytorch data for one status

            Input:
                - topic_names: list of topic name need to return,
                    default is None to return all available topics
                - status: status dictionary generated from this class,
                    default is None for current status
        """
        if status is None:
            status = self.current_status
        data = self.data(topic_names, [status], len(self.history_status))
        for k in data:
            data[k] = torch.tensor(data[k])
        return dialog_collate([data])        
        
