#!/usr/bin/env python3
import torch, sys
import torch.nn.functional as F
import torch.nn as nn
from .model_base import Model_Base

'''
    Author: Pengjia Zhu (zhupengjia@gmail.com)
'''

class Sentence_Encoder(Model_Base):
    '''
        sentence encoder to get the sentence embedding, use CNN. 
    '''
    def __init__(self, vocab, kernel_num, kernel_size, dropout=0.2):
        super().__init__(vocab)
        self.embedding = nn.Embedding(num_embeddings = self.vocab.vocab_size, \
                embedding_dim = self.vocab.embedding.dim, \
                padding_idx = self.vocab.PAD_ID)

        #self.embedding.weight.data = torch.FloatTensor(self.vocab.dense_vectors())
        #self.embedding.weight.requires_grad = False
        self.conv = nn.Conv2d(in_channels = 1, \
                out_channels = kernel_num, \
                kernel_size = (kernel_size, self.vocab.embedding.dim),\
                padding = 0)
        self.dropout = nn.Dropout(dropout)
        self.pool = nn.AvgPool1d(2)

    def conv_and_pool(self, x):
        x = self.embedding(x)
        x = x.unsqueeze(1)
        x = self.conv(x)
        x = F.relu(x)
        x = x.squeeze(3)
        x = self.pool(x)
        x = self.dropout(x)
        return x

    def forward(self, query):
        q = self.conv_and_pool(query)
        return q



