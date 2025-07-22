import numpy as np

from simulation import Simulation


def crossover(parent1: list[int], parent2: list[int]):
    mask = np.random.rand(len(parent1)) < 0.5
    return np.where(mask, parent1, parent2)


class GAOptimizer:
    def __init__(
            self,
            base: list[dict],
            optim_dict: dict,
            mutation_scale: float,
            generations:int,
            num_per_gen: int=1
    ):
        self.base: list[dict] = base
        self.optim_dict: dict = optim_dict
        self.num_per_gen: int = num_per_gen
        self.mutation_scale: float = mutation_scale
        self.generations: int = generations

        self.to_run: list[list[int]] = []
        self.changeable_dicts: list[dict] = []
        self.results: list[tuple[list[int], float]] = []

        for name in optim_dict['objects']:
            for region in base:
                if region.get('name', None) == name:
                    self.changeable_dicts.append(region)

    def start(self):
        self.init_population()
        self.run_generation()

        for i in range(self.generations - 1):
            self.next_generation()
            self.run_generation()

    def init_population(self):
        for _ in range(self.num_per_gen):
            added = False
            while not added:
                positions = np.random.choice(
                    np.arange(len(self.optim_dict['positions'])),
                    len(self.optim_dict['objects']),
                    replace=False
                ).tolist()

                for other in self.to_run:
                    if np.allclose(positions, other):
                        break
                else:
                    self.to_run.append(positions)
                    added = True

    def run(self, positions: list[int]):
        for (i, region) in enumerate(self.changeable_dicts):
            region.update(self.optim_dict['positions'][positions[i]])

        name = 'foam_case_' + '_'.join([str(i) for i in positions])

        sim = Simulation(self.base, name)
        sim.write_all()
        sim.run_all()
        self.results.append((positions, sim.get_results().max_temp()))
        print(positions, sim.get_results().max_temp())

    def run_generation(self):
        for positions in self.to_run:
            self.run(positions)

    def next_generation(self):
        self.to_run = []
        self.results.sort(key=lambda x: x[1], reverse=True)
        weights = np.exp(-np.linspace(0, len(self.results), len(self.results), dtype=np.float32))
        weights = weights / weights.sum()

        for i in range(self.num_per_gen):
            added = False
            while not added:
                parents = np.random.choice(
                    np.arange(len(self.results)),
                    2,
                    replace=True,
                    p=weights
                )
                parent1 = self.results[parents[0]][0]
                parent2 = self.results[parents[1]][0]

                child: list[int] = crossover(parent1, parent2).tolist()
                child = self.mutate(child)

                for pos in self.to_run:
                    if np.allclose(pos, child):
                        break
                else:
                    for pos, _ in self.results:
                        if np.allclose(pos, child):
                            break
                    else:
                        self.to_run.append(child)
                        added = True


    def mutate(self, child: list[int]):
        mutate_pos = np.random.randint(len(child))

        distances = []
        for (i, pos) in enumerate(self.optim_dict['positions']):
            if i in child and i != mutate_pos:
                distances.append(np.inf)
            else:
                child_box = self.optim_dict['positions'][child[mutate_pos]]
                child_corner = np.array([
                    child_box['x_min'],
                    child_box['y_min'],
                    child_box['x_min'],
                ])

                pos_corner = np.array([
                    pos['x_min'],
                    pos['y_min'],
                    pos['z_min'],
                ])
                distances.append(np.linalg.norm(child_corner - pos_corner))

        max_dist = np.random.exponential(scale=self.mutation_scale)
        weights = np.astype(np.array(distances) < max_dist, np.float32)
        if weights.sum() == 0:
            return child
        weights = weights / weights.sum()

        new_pos = np.random.choice(
            np.arange(len(self.optim_dict['positions'])),
            1,
            replace=False,
            p=weights
        )
        child[mutate_pos] = new_pos.tolist()[0]
        return child
