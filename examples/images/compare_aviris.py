"""Does not work with NamedConfig for unknown reason"""

from copy import copy
from os.path import expanduser

from decompose_images import decompose_ex, decompose_run
from data import data_ing
from sacred import Experiment
from sacred.observers import MongoObserver
from sklearn.externals.joblib import Parallel, delayed

compare_ex = Experiment('compare_aviris', ingredients=[decompose_ex])
observer = MongoObserver.create(url='172.18.0.16')
compare_ex.observers.append(observer)


@decompose_ex.config
def config():
    batch_size = 200
    learning_rate = 0.9
    offset = 0
    AB_agg = 'async'
    G_agg = 'full'
    Dx_agg = 'average'
    reduction = 1
    alpha = 1e-1
    l1_ratio = 0
    pen_l1_ratio = 1
    n_epochs = 10
    verbose = 50
    verbose_offset = 100
    n_components = 100
    n_threads = 3
    subset_sampling = 'random'
    dict_reduction = 'follow'
    temp_dir = expanduser('~/tmp')
    buffer_size = 5000
    test_size = 2000
    max_patches = None
    patch_shape = (16, 16)


@data_ing.config
def config():
    source = 'aviris'
    gray = False
    scale = 1

@compare_ex.config
def config():
    n_jobs = 2
    param_updates_list = [
        {'G_agg': 'average', 'Dx_agg': 'average', 'AB_agg': 'async'},
    ]
    config_updates_list = []
    reductions = [6, 12, 24]
    for param in param_updates_list:
        for reduction in reductions:
            config_updates_list.append(dict(reduction=reduction,
                                            **param))
    # Reference
    # config_updates_list.append({'G_agg': 'full',
    #                            'Dx_agg': 'full', 'AB_agg': 'full',
    #                            'reduction': 1})
    del param_updates_list, reductions, param

# Cannot capture in joblib
def single_run(our_config_updates, config, parent_id):
    @decompose_ex.capture
    def pre_run_hook(_run):
        print(parent_id)
        _run.info['parent_id'] = parent_id
        _run.info['updated_params'] = our_config_updates

    single_observer = MongoObserver.create(url='172.18.0.16')
    decompose_ex.pre_run_hooks = [pre_run_hook]
    decompose_ex.observers = [single_observer]

    config_updates = config['decompose_images'].copy()
    config_updates['seed'] = config['seed']
    for key, value in our_config_updates.items():
        config_updates[key] = value
    for ingredient in decompose_ex.ingredients:
        path = ingredient.path
        config_updates[path] = {}
        ingredient_config_update = config[path]
        config_updates[path]['seed'] = config['seed']
        for key, value in ingredient_config_update.items():
            config_updates[path][key] = value

    decompose_ex.run(config_updates=config_updates)


@compare_ex.automain
def compare_run(config_updates_list, n_jobs, _run):
    parent_id = _run.observers[0].run_entry['_id']
    config = _run.config
    Parallel(n_jobs=n_jobs,
             backend='multiprocessing')(
        delayed(single_run)(our_config_updates=our_config_updates,
                            parent_id=parent_id, config=config)
        for our_config_updates in config_updates_list)
