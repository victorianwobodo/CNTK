﻿# Copyright (c) Microsoft. All rights reserved.

# Licensed under the MIT license. See LICENSE.md file in the project root
# for full license information.
# ==============================================================================

import numpy as np
import os
import sys
from cntk.utils import cntk_device
from cntk.cntk_py import DeviceKind_GPU
from cntk.device import set_default_device
from cntk.io import ReaderConfig, ImageDeserializer
import pytest

abs_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(abs_path, "..", "..", "..", "..", "Examples", "Image", "Classification", "ConvNet", "Python"))
from CifarConvNet import train_and_evaluate, create_reader

TOLERANCE_ABSOLUTE = 2E-1

def test_cifar_convnet_error(device_id):
    if cntk_device(device_id).type() != DeviceKind_GPU:
        pytest.skip('test only runs on GPU')
    set_default_device(cntk_device(device_id))

    try:
        base_path = os.path.join(os.environ['CNTK_EXTERNAL_TESTDATA_SOURCE_DIRECTORY'],
                                *"Image/CIFAR/v0/cifar-10-batches-py".split("/"))
        # N.B. CNTK_EXTERNAL_TESTDATA_SOURCE_DIRECTORY has {train,test}_map.txt
        #      and CIFAR-10_mean.xml in the base_path.
    except KeyError:
        base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                *"../../../../Examples/Image/DataSets/CIFAR-10".split("/"))

    base_path = os.path.normpath(base_path)
    os.chdir(os.path.join(base_path, '..'))
    #os.chdir(os.path.join(base_path, '..'))    # (Frank's setup, will be changed back)

    from _cntk_py import set_computation_network_trace_level, set_fixed_random_seed, force_deterministic_algorithms
    set_computation_network_trace_level(1) 
    set_fixed_random_seed(1)  # BUGBUG: has no effect at present  # TODO: remove debugging facilities once this all works
    #force_deterministic_algorithms()
    # TODO: do the above; they lead to slightly different results, so not doing it for now

    reader_train = create_reader(os.path.join(base_path, 'train_map.txt'), os.path.join(base_path, 'CIFAR-10_mean.xml'), True)
    reader_test  = create_reader(os.path.join(base_path, 'test_map.txt'), os.path.join(base_path, 'CIFAR-10_mean.xml'), False)

    test_error = train_and_evaluate(reader_train, reader_test, max_epochs=5)
    expected_test_error = 0.463

    assert np.allclose(test_error, expected_test_error,
                       atol=TOLERANCE_ABSOLUTE)

    # enable this:
    #reader_train = create_reader(data_path, 'train_map.txt', 'CIFAR-10_mean.xml', is_training=True)
    #reader_test  = create_reader(data_path, 'test_map.txt',  'CIFAR-10_mean.xml', is_training=False)
    #loss_avg, evaluation_avg = train_and_evaluate(reader_train, reader_test, model, max_epochs=1)
    #print("-->", evaluation_avg, loss_avg)
    #expected_avg = [5.47968, 1.5783466666030883]
    #assert np.allclose([evaluation_avg, loss_avg], expected_avg, atol=TOLERANCE_ABSOLUTE)
    #
    ## save and load
    #path = data_path + "/model.cmf"
    #save_model(model, path)
    #model = load_model(path)
    #
    ## test
    #reader_test  = create_reader(data_path, 'test_map.txt', 'CIFAR-10_mean.xml', is_training=False)
    #evaluate(reader_test, model)

if __name__=='__main__':
    test_cifar_convnet_error(0)