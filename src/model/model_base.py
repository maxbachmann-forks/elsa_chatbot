#!/usr/bin/env python
import torch, sys
import torch.nn.functional as F
import torch.nn as nn

class Model_Base(nn.Module):
    def __init__(self, cfg, vocab):
        super().__init__()
        self.cfg = cfg
        self.vocab = vocab
    
    def attention(self, x, y):
        M = torch.bmm(x, y.transpose(1,2))
        M_rowsum = M.sum(dim=1)
        M_colsum = M.sum(dim=2)
        return torch.cat((M_rowsum, M_colsum), 1)

