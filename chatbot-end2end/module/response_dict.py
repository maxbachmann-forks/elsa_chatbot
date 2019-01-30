#!/usr/bin/env python
import sys, re, numpy
from nlptools.text import VecTFIDF
from nlptools.text.ngrams import Ngrams
from nlptools.utils import flat_list


'''
    Author: Pengjia Zhu (zhupengjia@gmail.com)
'''

class Response_Dict:
    '''
        Response dictionary. Used to index the response template and get the most closed response_template from a response string. 
        
        First you need a response template file, the format in each line is:  
            - needed_entity | notneeded_entity | func_call | response  
                - needed_entity means this response is available only those entities existed  
                - notneeded_entity means this response is not available if those entities existed  
                - func_call is the needed function call  before return the response. The available func_call is in src/hook/behaviors. In the future will support web hooks  
  
        The class will build a tf-idf index for template, the __getitem__ method is to get the most closed response via the tf-idf algorithm.(only used for training, the response string in training data will convert to a response id via tfidf search)  

        Input:
            - tokenizer: instance of nlptools.text.tokenizer
            - entity_dict: instance of src/module/entity_dict
            - cached_index: path of cached index file for response search, will create the file if it is not existed

        Special usage:
            - len(): return number of responses in template
            - __getitem__ : get most closed response id for response, input is response string
    '''
    def __init__(self, tokenizer, entity_dict, cached_index):
        self.response, self.response_ids, self.func_need = [], [], []
        self.entity_need = {'need':[], 'notneed':[]}
        self.tokenizer = tokenizer
        self.cached_vocab = cached_index + '.vocab'
        self.vocab = Ngrams(ngrams=3, cached_vocab = self.cached_vocab) #response vocab, only used for searching best matched response template, independent with outside vocab.  
        self.entity_dict = entity_dict
        self.__search = VecTFIDF(self.vocab, cached_index)


    def add(self, response):
        '''
            add a response to dictionary, only used when building the dictionary

            Input:
                - response: string, usually from response_template
        '''
        response = [x.strip() for x in response.split('|')]
        if len(response) < 3:
            return
        entity_need = {}
        try:
            entity_need['need'], entity_need['notneed'], func_need, response = tuple(response)
        except Exception as err:
            print("Error: Template error!!")
            print("Error sentence: " + ' | '.join(response))
            print("The format should be: needentity | notneedentity | func | response")
            sys.exit()

        response_lite = re.sub('(\{[A-Z]+\})|(\d+)','', response)
        response_ids = self.vocab.words2id(self.tokenizer(response_lite)) 
        response_ids = numpy.concatenate(list(response_ids.values()))
        if len(response_ids) < 1:
            return
        self.response.append(response)
        self.response_ids.append(response_ids)
        
        entity_need = {k:[x.strip() for x in re.split(',', entity_need[k])] for k in entity_need}
        entity_need = {k:[x.upper() for x in entity_need[k] if len(x) > 0] for k in entity_need}
        entity_need = {k:[self.entity_dict.name2id(x) for x in entity_need[k]] for k in entity_need}
        for k in self.entity_need: self.entity_need[k].append(entity_need[k])
        
        func_need = [x.strip() for x in re.split(',', func_need)]
        func_need = [x.lower() for x in func_need if len(x) > 0]
        self.func_need.append(func_need)


    def build_index(self):
        '''
            build search index for response template. no input needed. Use it after added all responses
        '''
        self.__search.load_index(self.response_ids)
        self.vocab.save()


    def __len__(self):
        '''
            get number of responses
        '''
        return len(self.response)


    def build_mask(self):
        '''
            build entity mask of response template, converted from the template
        '''
        entity_maskdict = sorted(list(set(flat_list(flat_list(self.entity_need.values())))))
        entity_maskdict = dict(zip(entity_maskdict, range(len(entity_maskdict))))
        self.masks = {'need': numpy.zeros((len(self.response), len(entity_maskdict)), 'bool_'), \
                'notneed': numpy.zeros((len(self.response), len(entity_maskdict)), 'bool_')}
        self.entity_dict.entity_maskdict = entity_maskdict #copy maskdict to entity_dict 
        for i in range(len(self.entity_need['need'])):
            for e in self.entity_need['need'][i]:
                self.masks['need'][i, entity_maskdict[e]] = True
        for i in range(len(self.entity_need['notneed'])):
            for e in self.entity_need['notneed'][i]:
                self.masks['notneed'][i, entity_maskdict[e]] = True
  

    def response2onehot(self, response_id):
        '''
            convert a response id to onehot present. used in dialog_tracker

            Input:
                - response_id: int

            Output:
                - 1d numpy array
        '''
        response = numpy.zeros(len(self.response), 'float')
        response[response_id] = 1
        return response

    def __getitem__(self, response_tokens):
        '''
            get most closed response id from templates
            
            Input:
                - response_tokens: list of string

            Output:
                - response_id, int. If not found return None.
        '''
        response_ids = self.vocab.words2id(response_tokens)
        response_ids = numpy.concatenate(list(response_ids.values()))
        if len(response_ids) < 1:
            return None
        result = self.__search.search_index(response_ids, topN=1)
        if len(result) > 0:
            return result[0]
        else:
            return None



