import cntk as C
import numpy as np
from bidaf import Bidaf
import os
import argparse
import importlib

model_name = "bidaf.model"

def argument_by_name(func, name):
    found = [arg for arg in func.arguments if arg.name == name]
    if len(found) == 0:
        raise ValueError('no matching names in arguments')
    elif len(found) > 1:
        raise ValueError('multiple matching names in arguments')
    else:
        return found[0]

def create_mb_and_map(func, data_file, bidaf, randomize):
    mb_source = C.MinibatchSource(C.CTFDeserializer(data_file, C.StreamDefs(
        context_g_words  = C.StreamDef('cgw', shape=bidaf.wg_dim, is_sparse=True),
        query_g_words    = C.StreamDef('qgw', shape=bidaf.wg_dim, is_sparse=True),
        context_ng_words = C.StreamDef('cnw', shape=bidaf.wn_dim, is_sparse=True),
        query_ng_words   = C.StreamDef('qnw', shape=bidaf.wn_dim, is_sparse=True),
        answer_begin     = C.StreamDef('ab',  shape=bidaf.a_dim,  is_sparse=False),
        answer_end       = C.StreamDef('ae',  shape=bidaf.a_dim,  is_sparse=False),
        context_chars    = C.StreamDef('cc',  shape=bidaf.c_dim,  is_sparse=True),
        query_chars      = C.StreamDef('qc',  shape=bidaf.c_dim,  is_sparse=True)
    )), randomize=randomize)

    input_map = {
        argument_by_name(func, 'cgw'): mb_source.streams.context_g_words,
        argument_by_name(func, 'qgw'): mb_source.streams.query_g_words,
        argument_by_name(func, 'cnw'): mb_source.streams.context_ng_words,
        argument_by_name(func, 'qnw'): mb_source.streams.query_ng_words,
        argument_by_name(func, 'cc' ): mb_source.streams.context_chars,
        argument_by_name(func, 'qc' ): mb_source.streams.query_chars,
        argument_by_name(func, 'ab' ): mb_source.streams.answer_begin,
        argument_by_name(func, 'ae' ): mb_source.streams.answer_end
    }
    return mb_source, input_map

def train(data_path, model_path, log_file, config_file, restore=False, profiling=False):
    bidaf = Bidaf(config_file)
    z, loss = bidaf.model()
    training_config = importlib.import_module(config_file).training_config
    mb_source, input_map = create_mb_and_map(loss, os.path.join(data_path, training_config['train_data']), bidaf, True)
    
    f1 = bidaf.f1_score(argument_by_name(loss, 'ab'), argument_by_name(loss, 'ae'), z.outputs[0], z.outputs[1])

    max_epochs = training_config['max_epochs']
    log_freq = training_config['log_freq']
    minibatch_size = training_config['minibatch_size']
    epoch_size = training_config['epoch_size']

    progress_writers = [C.ProgressPrinter(
                            num_epochs = max_epochs,
                            freq = log_freq,
                            tag = 'Training',
                            log_to_file = log_file,
                            rank = C.Communicator.rank(),
                            gen_heartbeat = False)]

    learner = C.adadelta(z.parameters, rho=0.5)

    if C.Communicator.num_workers() > 1:
        learner = C.data_parallel_distributed_learner(learner, num_quantization_bits=32, distributed_after=0)

    trainer = C.Trainer(z, (loss, f1), learner, progress_writers)

    if profiling:
        C.start_profiler(sync_gpu=True)

    C.training_session(
        trainer=trainer,
        mb_source = mb_source,
        mb_size = minibatch_size,
        var_to_stream = input_map,
        max_samples = epoch_size * max_epochs,
        checkpoint_config = C.CheckpointConfig(filename = os.path.join(model_path, model_name), restore=restore),
        progress_frequency = epoch_size
    ).train()
    
    if profiling:
        stop_profiler()

if __name__=='__main__':
    # default Paths relative to current python file.
    abs_path   = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(abs_path, 'Models')
    data_path  = os.path.join(abs_path, '.')

    parser = argparse.ArgumentParser()
    parser.add_argument('-datadir', '--datadir', help='Data directory where the dataset is located', required=False, default=data_path)
    parser.add_argument('-outputdir', '--outputdir', help='Output directory for checkpoints and models', required=False, default=None)
    parser.add_argument('-logdir', '--logdir', help='Log file', required=False, default=None)
    parser.add_argument('-profile', '--profile', help="Turn on profiling", action='store_true', default=False)
    parser.add_argument('-config', '--config', help='Config file', required=False, default='config')
    parser.add_argument('-r', '--restart', help='Indicating whether to restart from scratch (instead of restart from checkpoint file by default)', action='store_true')

    args = vars(parser.parse_args())

    if args['outputdir'] is not None:
        model_path = args['outputdir'] + "/models"
    if args['datadir'] is not None:
        data_path = args['datadir']

    try:
        train(data_path, model_path, args['logdir'], args['config'],
            restore = not args['restart'],
            profiling = args['profile'])
    finally:
        C.distributed.Communicator.finalize()
