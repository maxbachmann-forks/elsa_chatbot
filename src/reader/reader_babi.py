#!/usr/bin/env python
import glob, os, yaml, sys, re
from ailab.utils import zload, zdump, flat_list
from .reader_base import Reader_Base

class Reader_Babi(Reader_Base):
    def __init__(self, cfg):
        Reader_Base.__init__(self, cfg)
     
    def rm_index(self, row):
        return [' '.join(row[0].split(' ')[1:])] + row[1:]

    def read(self, filename):
        cached_pkl = filename + '.pkl'
        if os.path.exists(cached_pkl):
            convs = zload(cached_pkl)
        else:
            convs = []
            with open(filename) as f:
                conv = []
                utterance, response = '', ''
                for l in f:
                    l = l.strip()
                    l = self.rm_index(l.split('\t'))
                    if l[0][:6] == 'resto_':
                        utterance, response = '', ''
                        continue
                    if len(l) < 2:
                        if len(utterance) > 0 and len(response) > 0 :
                            conv.append([utterance, response])
                        if len(conv) > 0 :
                            convs.append(conv)
                            conv = []
                        utterance, response = '', ''
                    else:
                        if l[0] == '<SILENCE>' :
                            if l[1][:8] != 'api_call':
                                response += '\n' + l[1]
                        else:
                            if len(utterance) > 0 and len(response) > 0 :
                                conv.append([utterance, response])
                            utterance, response = '', ''
                            utterance = l[0]
                            response = l[1]
                if len(utterance) > 0 and len(response) > 0 :
                    conv.append([utterance, response])
                if len(conv) > 0:
                    convs.append(conv)
            
            convs = self.predeal(convs)
            zdump(convs, cached_pkl)
        self.responses.build_mask()
        self.data = convs



