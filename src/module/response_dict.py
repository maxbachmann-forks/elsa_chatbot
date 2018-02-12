#!/usr/bin/env python
import sys, re, numpy
from nlptools.text import VecTFIDF
from nlptools.utils import flat_list

class Response_Dict(object):
    def __init__(self, cfg, vocab):
        self.response, self.response_ids, self.entity_need, self.func_need = [], [], [], []
        self.vocab = vocab
        self.cfg = cfg
        self.__search = VecTFIDF(self.cfg, self.vocab)

    def add(self, response):
        response = [x.strip() for x in response.split('|')]
        if len(response) < 3:
            return
        entity_need, func_need, response = tuple(response)
        response = re.sub('(\{[A-Z]+\})|(\d+)','', response)
        response_ids = self.vocab.sentence2id(response, ngrams=3) 
        if len(response_ids) < 1:
            return
        self.response.append(response)
        self.response_ids.append(response_ids)
        entity_need = [x.strip() for x in re.split(',', entity_need)]
        func_need = [x.strip() for x in re.split(',', func_need)]
        entity_need = [x.upper() for x in entity_need if len(x) > 0]
        func_need = [x.lower() for x in func_need if len(x) > 0]
        self.entity_need.append(entity_need)
        self.func_need.append(func_need)


    def build_index(self):
        self.__search.load_index(self.response_ids)
        self.entities = list(set(flat_list(self.entity_need)))
        self.entities = dict(zip(self.entities, range(len(self.entities))))
        self.masks = numpy.zeros((len(self.response), len(self.entities)), 'bool_')
        for i in range(len(self.entity_need)):
            for e in self.entity_need[i]:
                self.masks[i, self.entities[e]] = True
   

    def __getitem__(self, response):
        response_ids = self.vocab.sentence2id(response, ngrams=3)
        if len(response_ids) < 1:
            return None
        result = self.__search.search_index(response_ids, topN=1)
        if len(result) > 0:
            return result[0]
        else:
            return None



