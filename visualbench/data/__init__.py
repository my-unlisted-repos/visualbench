import os

import numpy as np
import torch
from torch.nn import functional as F

from ..utils import to_3HW
from ..utils.image import _imread
_path = os.path.dirname(__file__)

QRCODE96 = os.path.join(_path, 'qr-96.jpg')
ATTNGRAD96 = os.path.join(_path, 'attngrad-96.png')
SANIC96 = os.path.join(_path, 'sanic-96.jpg')
TEST96 = os.path.join(_path, 'test-96.jpg')
MAZE96 = os.path.join(_path, 'maze-96.png')
TEXT96 = os.path.join(_path, 'text-96.png')

def get_qrcode():
    qrcode = to_3HW(_imread(QRCODE96).float()).mean(0)
    return torch.where(qrcode > 128, 1, 0).float().contiguous()

def get_maze():
    qrcode = to_3HW(_imread(MAZE96).float()).mean(0)
    return torch.where(qrcode > 128, 1, 0).float().contiguous()

def get_randn(size:int = 64):
    return torch.randn(size, size, generator = torch.Generator('cpu').manual_seed(0))

def get_circulant(size: int = 64):
    import scipy.linalg
    generator = np.random.default_rng(0)
    c = generator.uniform(-1, 1, (3, size))
    return torch.from_numpy(scipy.linalg.circulant(c).copy()).float().contiguous()

def get_dft(size: int = 96):
    import scipy.linalg
    dft = np.stack([scipy.linalg.dft(size).real, scipy.linalg.dft(96).imag], 0)
    return torch.from_numpy(dft).float().contiguous()

def get_fielder(size: int = 64):
    import scipy.linalg
    generator = np.random.default_rng(0)
    c = generator.uniform(-1, 1, (3, size))
    return torch.from_numpy(scipy.linalg.fiedler(c).copy()).float().contiguous()

def get_hadamard(size: int = 64):
    import scipy.linalg
    return torch.from_numpy(scipy.linalg.hadamard(size, float).copy()).float().contiguous() # pyright:ignore[reportArgumentType]

def get_helmert(size: int = 64):
    import scipy.linalg
    return torch.from_numpy(scipy.linalg.helmert(size).copy()).float().contiguous() # pyright:ignore[reportArgumentType]

def get_hilbert(size: int = 64):
    import scipy.linalg
    return torch.from_numpy(scipy.linalg.hilbert(size).copy()).float().contiguous() # pyright:ignore[reportArgumentType]

def get_invhilbert(size: int = 64):
    import scipy.linalg
    return torch.from_numpy(scipy.linalg.invhilbert(size).copy()).float().contiguous() # pyright:ignore[reportArgumentType]

def get_3d_structured48():
    qr = get_qrcode() # (96x96)
    attn = to_3HW(ATTNGRAD96) # (3x96x96)
    sanic = to_3HW(SANIC96)
    test = to_3HW(TEST96)

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

