The plan originally included running `bin/dev.sh test`, which builds the Rust code and runs coordinator tests, both of which are failing due to missing dependencies and pre-existing compilation errors that are outside the scope of my python refactoring task for `worker/benchmark.py`.

The changes I made only affect the Python code in `worker/benchmark.py` and its corresponding tests in `worker/tests/unit/test_benchmark.py`.

I have successfully run these Python unit tests using `unittest` and confirmed that my refactoring hasn't broken them and works correctly:
`PYTHONPATH=$PYTHONPATH:worker python3 -m unittest worker/tests/unit/test_benchmark.py`
