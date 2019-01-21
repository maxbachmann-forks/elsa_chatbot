#!/usr/bin/env python2
# -*- coding: utf-8 -*-
import numpy, pandas, re, random, math, sys
from nlptools.utils import Config
from nlptools.text import DocSim, Tokenizer, Embedding
from ..reader.rulebased import Reader

'''
    Author: Pengjia Zhu (zhupengjia@gmail.com)
'''

class Rule_Based:
    '''
        Rule based chatbot

        Input:
            - bert_model_name: bert model file location or one of the supported model name
            - hook: hook instance, please check src/hook/babi_gensays.py for example
            - dialog_file: xlsx file of rule definition
            - min_score: score filter for sentence similarity
    '''
    def __init__(self, bert_model_name, hook, dialog_file, min_score=0.6):
        self.bert_model_name = bert_model_name
        self.hook = hook
        self.docsim = DocSim(self.vocab)
        self.reader = Reader(dialog_file)
        self.tokenizer = tokenizer
        self.min_score = min_score
        self.session = {}
        self._predeal()


    @classmethod
    def build(cls, config, hook):
        '''
            construct model from config

            Input:
                - config: configure dictionary
                - hook: hook instance, please check src/hook/babi_gensays.py for example
        '''
        tokenizer = Tokenizer(tokenizer='bert', **config.tokenizer)
        embedding = Embedding(**config.embedding)
        vocab = tokenizer.vocab
        vocab.embedding = embedding
        return cls(vocab, tokenizer, hook=hook, dialog_file=config.dialog_file, min_score = config.min_score)


    def _predeal(self):
        '''
            predeal the dialogs
        '''
        def utterance2id(utter):
            if not isinstance(utter, str):
                return None
            utter = [self.vocab.words2id(self.tokenizer(u)) for u in re.split('\n', utter)]
            utter = [u for u in utter if len(u) > 0]
            if len(utter) < 1: return None
            return utter
        self.reader.data['utterance'] = self.reader.data['userSays'].apply(utterance2id)


    def get_reply(self, utterance, clientid):
        '''
            get response from utterance

            Input:
                - utterance: string
                - entities: dictionary
        '''
        #special command
        utterance = utterance.strip()
        if utterance in [':CLEAR', ':RESET', ':RESTART', ":EXIT", ":STOP", ":QUIT", ":Q"]:
            self.reset(clientid)
            return 'dialog status reset!'
        
        #create new session for user
        if not clientid in self.session:
            self.session[clientid] = {'CHILDID': None, 'RESPONSE': None}

        utterance_id = self.vocab.words2id(self.tokenizer(utterance))
        self.session[clientid]['RESPONSE'] = None # clean response
        if len(utterance_id) < 1:
            for e, v in self._get_fallback(self.session[clientid]).items():
                self.session[clientid][e] = v
        else:
            for e, v in self._find(utterance_id, self.session[clientid]).items():
                self.session[clientid][e] = v
        if isinstance(self.session[clientid]['RESPONSE'], str):
            return self.session[clientid]['RESPONSE']
        return '^_^'
    

    def reset(self, clientid):
        '''
            reset session
        '''
        if clientid in self.session:
            del self.session[clientid]


    def _find(self, utterance_id, entities):
        '''
            find the most closed one
            
            Input:
                - utterance_id : utterance token id list
                - entities: dictionary, current entities
        '''
        def getscore(utter_cand):
            if utter_cand is None: 
                return 0
            distance = min([self.docsim.rwmd_distance(utterance_id, u) for u in utter_cand])
            return 1/(1+distance)
        data = self.reader.data
        
        if entities['CHILDID'] is not None:
            data_filter = data.loc[entities['CHILDID']]
            data_filter['score'] = data_filter['utterance'].apply(getscore)
            idx = data_filter['score'].idxmax()
            if data_filter.loc[idx]['score'] < self.min_score:
                #try to get score for out of rules
                otherids = list(set(list(data.index)) - set(entities['CHILDID']))
                data_others = data.loc[otherids]
                data_others['score'] = data_others['utterance'].apply(getscore)
                idx_others = data_others['score'].idxmax()
                if data_others.loc[idx_others]['score'] > data_filter.loc[idx]['score']:
                    idx = idx_others
        else:
            data['score'] = data['utterance'].apply(getscore)
            idx = data['score'].idxmax()
        return self._get_response(data.loc[[idx]], entities)


    def _get_fallback(self, entities):
        '''
            get fallback, if there is NaN in userSays then pick one of them 

            Input:
                - entities: dictionary, current entities
        '''
        data = self.reader.data[pandas.isnull(self.reader.data.userSays)]
        if len(data) < 1:
            return {}
        return self._get_response(data, entities)


    def _get_response(self, data, entities):
        '''
            get response from data

            Input:
                - data: dataframe
                - entities: dictionary, current entities
        '''
        data = data.loc[random.choice(data.index)] # random pickup one
        if isinstance(data.webhook, str):
            entities = self._call_hook(data.webhook, entities)
        if not isinstance(entities['RESPONSE'], str) and isinstance(data.response, str):
            entities['RESPONSE'] = data.response
        if data.childID is not None:
            entities['CHILDID'] = self.__decode_childID(data.childID)
        else:
            entities['CHILDID'] = None
        return entities

        
    def _call_hook(self, hooks, entities):
        hooks = [y for y in [x.strip() for x in re.split('\s,;', hooks)] if len(y) > 0]
        for hook in hooks:
            func = getattr(self.hook, hook)
            if func is not None:
                for e, v in func(entities).items():
                    entities[e] = v
        return entities
        

    def __decode_childID(self, IDs):
        if isinstance(IDs, str):
            IDs2 = []
            for i in re.split('[,，]', IDs):
                if i.isdigit():
                    IDs2.append(int(i))
                else:
                    itmp = [int(x) for x in re.split('[~-]', i) if len(x.strip())>0]
                    if len(itmp) > 1:
                        IDs2 += range(itmp[0], itmp[1]+1)
                    else:
                        IDs2.append(int(itmp[0]))

            return numpy.asarray(IDs2, 'int')
        else:
            return numpy.asarray(IDs, 'int')

            
         


