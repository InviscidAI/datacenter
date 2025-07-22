from pathlib import Path

from simulation import Simulation


class BinarySearchOptimizer:
    def __init__(
            self,
            base,
            low,
            high,
            update_func,
            check_func,
            foam_case_dir='foam_case_binary_search',
            tol=None,
            max_iters=None
    ):
        if tol is None and max_iters is None:
            raise ValueError("Either tol or max_iters must be specified")

        self.base = base
        self.low = low
        self.high = high
        self.update_func = update_func
        self.check_func = check_func
        self.foam_case_dir = Path(foam_case_dir).absolute()
        self.tol = tol
        self.max_iters = max_iters

        self.iters = 0

    def next_iter(self):
        mid = (self.high + self.low) / 2

        updated = self.update_func(self.base, mid)

        sim = Simulation(updated, self.foam_case_dir, overwrite=True)
        sim.write_all()
        sim.run_all()

        if self.check_func(sim.get_results()):
            self.low = mid
        else:
            self.high = mid

    def run(self):
        while self.max_iters is None or self.iters < self.max_iters:
            self.next_iter()
            self.iters += 1

            if self.high - self.low < self.tol:
                return self.low


def check_max_temp(results, max_temp):
    print("max_temp: ", results.max_temp())
    return results.max_temp() <= max_temp


def update_set_temp(base, set_temp):
    updated = base.copy()
    print("update_set_temp: ", set_temp)
    for region in updated:
        if region['type'] == 'cooler':
            region['set_temp'] = set_temp

    return updated
