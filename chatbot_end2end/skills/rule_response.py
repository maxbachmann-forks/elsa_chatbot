#!/usr/bin/env python


"""
    Author: Pengjia Zhu (zhupengjia@gmail.com)
"""

class RuleResponse(SkillBase):
    '''
        Rule based skill
    '''
    def __init__(self, tokenizer, dialog_file, **args):
        pass

    def init_model(self, **args):
        """
            Initialize model
            
            Input:
                - saved_model: str, default is "dialog_tracker.pt"
                - device: string, model location, default is 'cpu'
                - see ..model.generative_tracker.Generative_Tracker for more parameters if path of saved_model not existed
        """
        
        pass

    def update_mask(self, current_status):
        return 0

    def get_response(self, current_status):
        return 0

    def update_response(self, response, current_status):
        return 0

    
    @classmethod
    def build(cls, config, hook):
        '''
            construct model from config

            Input:
                - config: configure dictionary
                - hook: hook instance, please check src/hook/babi_gensays.py for example
        '''
        logger = setLogger(**config.logger)
        device = torch.device("cuda:0" if config.use_gpu and torch.cuda.is_available() else "cpu")

        return cls(bert_model_name=config.bert_model_name, hook=hook, dialog_file=config.dialog_file, min_score = config.min_score, batch_size=config.batch_size, device=device, logger=logger)


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
        utterance_embeddings = numpy.concatenate(list(self.embedding(self.reader.data['userSays'].tolist())))
        self.reader.data['utterance'] = list(utterance_embeddings)


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

        self.session[clientid]['RESPONSE'] = None # clean response
        self.logger.debug('utterance: ' + utterance)
        if len(utterance) < 1:
            for e, v in self._get_fallback(self.session[clientid]).items():
                self.session[clientid][e] = v
        else:
            utterance_embedding = list(self.embedding(utterance))[0][0]
            for e, v in self._find(utterance_embedding, self.session[clientid]).items():
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


    def _find(self, utterance_embedding, entities):
        '''
            find the most closed one
            
            Input:
                - utterance_embedding : 1d array, embedding of utterance
                - entities: dictionary, current entities
        '''
        def getscore(utter_cand):
            if utter_cand is None: 
                return 0
            distance = cosine(utterance_embedding, utter_cand)
            return 1/(1+distance)
        data = self.reader.data
        
        if entities['CHILDID'] is not None:
            data_filter = data.loc[entities['CHILDID']]
            data_filter['score'] = data_filter['utterance'].apply(getscore)
            self.logger.debug("score: \n" + str(data_filter[['userSays', 'score', 'utterance']]))
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
        if isinstance(data.hook, str):
            entities = self._call_hook(data.hook, entities)
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
