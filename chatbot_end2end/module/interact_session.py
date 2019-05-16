#!/usr/bin/env python
import torch
from nlptools.text.tokenizer import Tokenizer_BERT
from nlptools.utils import setLogger
from nlptools.text.ner import NER
from .nltk_sentiment import NLTKSentiment
from .dialog_status import DialogStatus
from .topic_manager import TopicManager
from .. import skills as Skills
from ..reader import ReaderXLSX


'''
    Author: Pengjia Zhu (zhupengjia@gmail.com)
'''


class InteractSession:
    def __init__(self, vocab, tokenizer, ner, topic_manager,
                 sentiment_analyzer, max_seq_len=100,
                 max_entity_types=1024, device='cpu', logger=None, **args):
        """
            General interact session

            Input:
                - vocab:  instance of nlptools.text.vocab
                - tokenizer:  instance of nlptools.text.Tokenizer
                - ner: instance of nlptools.text.ner
                - topic_manager: instance of topic manager,
                    see ..module.topic_manager
                - sentiment_analyzer: sentiment analyzer instance
                - max_seq_len: int, maximum sequence length
                - max_entity_types: int, maximum entity types
                - device: string of torch device, default is "cpu"
                - logger: logger instance ,default is None
        """

        super().__init__()
        self.logger = logger
        self.device = torch.device(device)
        self.tokenizer = tokenizer
        self.vocab = vocab
        self.ner = ner
        self.sentiment_analyzer = sentiment_analyzer
        self.topic_manager = topic_manager
        self.max_seq_len = max_seq_len
        self.max_entity_types = max_entity_types
        self.dialog_status = {}

    @classmethod
    def build(cls, config):
        """
            construct session from config

            Input:
                - config: configure dictionary
        """
        # logger, tokenizer and ner
        logger = setLogger(**config.logger)
        tokenizer = Tokenizer_BERT(**config.tokenizer)
        if "ner" in config:
            ner_config = config.ner
        else:
            ner_config = None
        vocab = tokenizer.vocab
        sentiment_analyzer = NLTKSentiment()

        shared_layers = {}

        # skills
        topic_manager = TopicManager()
        for skill_name in config.skills:
            response_params = config.skills[skill_name]
            if not hasattr(Skills, config.skills[skill_name].wrapper):
                raise RuntimeError(
                    "Error!! Skill {} not implemented!".format(
                        config.skills[skill_name].wrapper))
            skill_cls = getattr(Skills, config.skills[skill_name].wrapper)
            if "dialogflow" in config.skills[skill_name]:
                dialogflow = ReaderXLSX(config.skills[skill_name].dialogflow,
                                        tokenizer=tokenizer,
                                       ner_config=ner_config) 
                entities = dialogflow.entities
                response_params.pop('dialogflow')
            else:
                dialogflow = None
                entities = None
            response_params.pop('wrapper')

            response = skill_cls(tokenizer=tokenizer, vocab=vocab,
                                 dialogflow=dialogflow,
                                 max_seq_len=config.model.max_seq_len,
                                 skill_name=skill_name,
                                 **response_params)
            response.init_model(
                shared_layers=shared_layers,
                device=config.model.device,
                **config.skills[skill_name])
            response.eval() # set to eval mode
            topic_manager.register(skill_name, response)

            if ner_config is not None and entities is not None:
                for k in ["keywords", "regex", "ner_name_replace"]:
                    if entities[k]:
                        if not k in ner_config:
                            ner_config[k] = {}
                        ner_config[k].update(entities[k])
                for k in ["ner"]:
                    if entities[k]:
                        if not k in ner_config:
                            ner_config[k] = []
                        ner_config[k] += entities[k]

        if ner_config is not None:
            ner = NER(**ner_config)
        else:
            ner = None

        return cls(vocab=vocab, tokenizer=tokenizer, ner=ner,
                   topic_manager=topic_manager, logger=logger,
                   sentiment_analyzer=sentiment_analyzer, **config.model)

    def new_dialog(self):
        return DialogStatus.new_dialog(self.vocab, self.tokenizer,
                                       self.ner, self.topic_manager,
                                       self.sentiment_analyzer,
                                       self.max_seq_len, self.max_entity_types)

    def response(self, query, response_sentiment=0, session_id="default"):
        """
            get response

            Input:
                - query: string
                - response_sentiment: float between -1 and 1, wanted sentiment of response, default is 0
                - session_id: string, session id, default is "default"
        """
        #create new session for user
        if session_id not in self.dialog_status:
            self.dialog_status[session_id] = self.new_dialog()

        #special commands
        if query in ["clear", "reset", "restart", "exit", "stop", "quit", "q"]:
            self.dialog_status[session_id] = self.new_dialog()
            return "reset"

        if query in ["debug"]:
            return str(self.dialog_status[session_id])

        if len(query) < 1 or self.dialog_status[session_id].add_utterance(query) is None:
            return self.dialog_status[session_id].get_fallback()

        response = self.dialog_status[session_id].get_response(response_sentiment, self.device)

        if "SESSION_RESET" in self.dialog_status[session_id].current_status["entity"]:
            del self.dialog_status[session_id]

        return response


