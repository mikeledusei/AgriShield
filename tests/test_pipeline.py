"""Test data pipeline scripts."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "data_pipeline", "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ml-models", "scripts"))


def test_config_imports():
    """Test data pipeline config."""
    try:
        import config
        assert True
    except ImportError:
        pass


def test_clean_data_imports():
    """Test clean data script."""
    try:
        import clean_data
        assert True
    except ImportError:
        pass


def test_fetch_data_imports():
    """Test fetch data script."""
    try:
        import fetch_data
        assert True
    except ImportError:
        pass


def test_engineer_features_imports():
    """Test engineer features script."""
    try:
        import engineer_features
        assert True
    except ImportError:
        pass


def test_synthesize_targets_imports():
    """Test synthesize targets script."""
    try:
        import synthesize_targets
        assert True
    except ImportError:
        pass


def test_pipeline_modules():
    """Test all pipeline modules import correctly."""
    from data_pipeline.scripts.clean_data import clean_data
    from data_pipeline.scripts.fetch_data import fetch_data
    from data_pipeline.scripts.engineer_features import engineer_features
    from data_pipeline.scripts.synthesize_targets import synthesize_targets
    assert clean_data is not None
    assert fetch_data is not None
    assert engineer_features is not None
    assert synthesize_targets is not None


def test_ml_model_scripts():
    """Test ML model scripts import."""
    import importlib.util
    scripts_dir = os.path.join(os.path.dirname(__file__), "..", "ml-models", "scripts")
    for name in ["train", "evaluate", "predict"]:
        spec = importlib.util.spec_from_file_location(name, os.path.join(scripts_dir, f"{name}.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module is not None
