import os

import torch
from myai.loaders.image import imreadtensor
from torch.nn import functional as F

from .._utils import _make_float_3hw_tensor

_path = os.path.dirname(__file__)

QRCODE96 = os.path.join(_path, 'qr-96.jpg')
ATTNGRAD96 = os.path.join(_path, 'attngrad-96.png')
SANIC96 = os.path.join(_path, 'sanic-96.jpg')
TEST96 = os.path.join(_path, 'test-96.jpg')


def get_qrcode():
    qrcode = imreadtensor(QRCODE96).float().mean(0)
    return torch.where(qrcode > 128, 1, 0).float().contiguous()

def get_randn():
    return torch.randn(64,64, generator = torch.Generator('cpu').manual_seed(0))


def get_3d_structured48():
    qr = get_qrcode() # (96x96)
    attn = _make_float_3hw_tensor(ATTNGRAD96) # (3x96x96)
    sanic = _make_float_3hw_tensor(SANIC96)
    test = _make_float_3hw_tensor(TEST96)

    qr = qr.unfold(0, 48, 48).unfold(1, 48, 48).flatten(0,1) # 4,48,48
    qr = torch.cat([qr, qr.flip(0), qr.flip(1)]) # 12,48,48
    attn = attn.unfold(1, 48, 48).unfold(2, 48, 48).flatten(0,2) # 12,48,48
    sanic = attn.unfold(1, 48, 48).unfold(2, 48, 48).flatten(0,2) # 12,48,48
    test = attn.unfold(1, 48, 48).unfold(2, 48, 48).flatten(0,2) # 12,48,48

    stacked = torch.cat([qr,attn,sanic,test]) # 48,48,48
    # make dims varied
    stacked[:12] = attn
    stacked = stacked.transpose(0, 1)
    stacked[:12] = test
    stacked = stacked.transpose(0,2)
    stacked[:12] = qr

    return stacked

