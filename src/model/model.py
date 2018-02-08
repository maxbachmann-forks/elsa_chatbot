#!/usr/bin/env python3
import torch, sys
import torch.nn.functional as F
import torch.nn as nn

class Dialog_Track(nn.Module):
    def __init__(self, cfg, vocab):
        super().__init__()
        self.cfg = cfg
        self.vocab = vocab
        self.network()
    
    def network(self):
        self.embedding = nn.Embedding(num_embeddings = self.vocab.vocab_size, \
                embedding_dim = self.vocab.emb_ins.vec_len, \
                padding_idx = self.vocab._id_PAD)

        self.embedding.weight.data = torch.FloatTensor(self.vocab.dense_vectors())
        #self.embedding.weight.requires_grad = False
        self.conv = nn.Conv2d(in_channels = 1, \
                out_channels = self.cfg['cnn_kernel_num'], \
                kernel_size = (self.cfg['cnn_kernel_size'], self.vocab.emb_ins.vec_len),\
                padding = 0)
        self.pool = nn.AvgPool1d(2)
        self.fc1 = nn.Linear(self.cfg['cnn_kernel_num']*2, 1)
        self.sigmoid = nn.Sigmoid()

    def conv_and_pool(self, x):
        x = self.embedding(x)
        x = x.unsqueeze(1)
        x = self.conv(x)
        x = x.squeeze(3)
        x = self.pool(x)
        return x

    def forward(self, data):
        q = self.conv_and_pool(data['query'])


