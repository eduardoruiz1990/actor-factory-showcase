import json


def dataset_items(storage):
    folder = storage / 'datasets' / 'default'
    files = sorted((p for p in folder.glob('*.json') if p.name != '__metadata__.json'), key=lambda p: p.name)
    return [json.loads(p.read_text()) for p in files]
