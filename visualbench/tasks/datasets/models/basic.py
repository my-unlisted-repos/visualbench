from functools import partial
from typing import Literal
from collections.abc import Callable

import torch
from myai import nn as mynn
from torch import nn
from torch.nn import functional as F


class _MLP(nn.Module):
    def __init__(self, in_channels, out_channels, hidden, act: Callable | None = F.relu, bn = False, dropout:float=0, cls: Callable = nn.Linear):
        super().__init__()
        if isinstance(hidden, int): hidden = [hidden]
        if hidden is None: hidden = []
        channels = [in_channels] + list(hidden) + [out_channels]

        layers = []
        for i,o in zip(channels[:-2], channels[1:-1]):
            layer = [cls(i, o, not bn), act if act is not None else nn.Identity(), nn.BatchNorm1d(o) if bn else nn.Identity(), nn.Dropout(dropout) if dropout>0 else nn.Identity()]
            layers.append(mynn.Sequential(*layer))

        self.layers = mynn.Sequential(*layers)
        self.head = cls(channels[-2], channels[-1])

    def forward(self, x):
        for l in self.layers: x = l(x)
        return self.head(x)

def MLP(hidden, act: Callable | None = F.relu, bn = False, dropout:float=0, cls: Callable = nn.Linear):
    return partial(_MLP, hidden = hidden, act = act, bn = bn, dropout = dropout, cls = cls)

class _RecurrentMLP(nn.Module):
    def __init__(
        self,
        in_channels,
        out_channels,
        width,
        n_passes,
        merge: bool = True,
        act: Callable | None = F.leaky_relu,
        dropout: float = 0,
        bn=True,
        cls: Callable = nn.Linear,
    ):
        super().__init__()
        self.n_passes = n_passes
        if merge and in_channels == width: in_channels = None
        self.first = cls(in_channels, width) if in_channels is not None else nn.Identity()
        linear = cls(width,width, not bn)
        self.rec = mynn.Sequential(linear, act if act is not None else nn.Identity())
        self.batch_norms = nn.ModuleList([nn.BatchNorm1d(width) if bn else nn.Identity() for _ in range(n_passes)])
        self.drop = nn.Dropout(dropout) if dropout > 0 else nn.Identity()

        self.head = cls(width,out_channels)

    def forward(self, x):
        x = self.first(x)
        for bn in self.batch_norms: x = self.drop(bn(self.rec(x)))
        return self.head(x)

def RecurrentMLP(width, n_passes, merge: bool = True, act: Callable | None = F.leaky_relu, dropout: float = 0, bn = True, cls: Callable = nn.Linear):
    return partial(_RecurrentMLP, width=width, n_passes=n_passes, merge=merge, act=act, dropout=dropout, bn = bn, cls=cls)


class _Mnist1dLSTM(nn.Module):
    def __init__(self, in_channels, out_channels, hidden_size, num_layers):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.lstm = nn.LSTM(1, hidden_size, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, out_channels)

    def forward(self, x):
        x = x.unsqueeze(2) # from (batch_size, 40) to (batch_size, 40, 1) otherwise known as (batch_size, seq_length, input_size)

        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)# hidden state
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device) # cell state

        # LSTM forward pass
        out, _ = self.lstm(x, (h0, c0)) # out: (batch_size, seq_length, hidden_size)
        out = out[:, -1, :] # last timestep's output (batch_size, hidden_size)
        out = self.fc(out) # (batch_size, num_classes)
        return out

def Mnist1dLSTM(hidden_size, num_layers):
    return partial(_Mnist1dLSTM, hidden_size=hidden_size, num_layers=num_layers)

class _Mnist1dConvNet(torch.nn.Module):
    def __init__(self, in_channels, out_channels, hidden = (32, 64, 128, 256), act = 'relu', norm = 'fixedbn', dropout=None):
        super().__init__()
        if isinstance(hidden, int): hidden = [hidden]
        channels = [1] + list(hidden) # in_channels is always 1 cos conv net

        self.enc = torch.nn.Sequential(
            *[mynn.ConvBlock(i, o, 2, 2, act=act, norm=norm, ndim=1, dropout=dropout) for i, o in zip(channels[:-1], channels[1:])]
        )
        self.head = mynn.LinearBlock(channels[-1]*2, out_channels, flatten=True)

    def forward(self, x):
        if x.ndim == 2: x = x.unsqueeze(1)
        x = self.enc(x)
        return self.head(x)

def Mnist1dConvNet(hidden = (32, 64, 128, 256), act = 'relu', norm = 'fixedbn', dropout=None):
    """only for mnist1d"""
    return partial(_Mnist1dConvNet, hidden = hidden, act = act, norm = norm, dropout=dropout)


class _Mnist1dRecurrentConvNet(torch.nn.Module):
    def __init__(self, in_channels, out_channels, width: int = 64,num: int = 4, act = 'relu', norm = 'fixedbn'):
        super().__init__()
        self.first = mynn.ConvBlock(1, width, 2, 2, act=act, norm=norm, ndim = 1)
        self.rec = mynn.ConvBlock(width, width, 2, 2, act=act, norm=norm, ndim = 1)
        self.head = mynn.LinearBlock(width, out_channels, flatten=True)
        self.num = num

    def forward(self, x):
        if x.ndim == 2: x = x.unsqueeze(1)
        x = self.first(x)
        for _ in range(self.num): x = self.rec(x)
        return self.head(x)

def Mnist1dRecurrentConvNet(width = 64, act = 'relu', norm = 'fixedbn'):
    return partial(_Mnist1dRecurrentConvNet, width = width, act = act, norm = norm)

