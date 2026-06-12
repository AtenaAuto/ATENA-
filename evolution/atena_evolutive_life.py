#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 ATENA Ω - Simulador de Vida Artificial Evolutiva (SVAE) v1.1.0
Implementação com coleta de dados históricos para análise de insights.
"""

import numpy as np
import random
import json
import os
from datetime import datetime

class Organism:
    def __init__(self, dna=None):
        if dna is None:
            self.dna = np.random.uniform(-1, 1, (4, 2))
        else:
            self.dna = dna
        
        self.energy = 100.0
        self.age = 0
        self.fitness = 0
        self.alive = True

    def think(self, inputs):
        inputs = np.array(inputs)
        outputs = np.tanh(np.dot(inputs, self.dna))
        return outputs

    def update(self, inputs):
        if not self.alive:
            return
        
        outputs = self.think(inputs)
        accel, rotate = outputs
        cost = (abs(accel) + abs(rotate)) * 0.1 + 0.05
        self.energy -= cost
        self.age += 1
        self.fitness += 0.1
        
        if self.energy <= 0:
            self.alive = False

class Environment:
    def __init__(self, pop_size=50):
        self.pop_size = pop_size
        self.population = [Organism() for _ in range(pop_size)]
        self.generation = 1
        self.history = []

    def run_generation(self, steps=100):
        print(f"🧬 Geração {self.generation} em curso...")
        for _ in range(steps):
            for org in self.population:
                if org.alive:
                    dist_food = random.random() * 10
                    inputs = [dist_food, org.energy/100.0, 0.5, org.age/100.0]
                    org.update(inputs)
                    if random.random() < 0.05:
                        org.energy = min(100, org.energy + 20)
                        org.fitness += 5

        self.collect_stats()
        self.evolve()

    def collect_stats(self):
        fitness_scores = [org.fitness for org in self.population]
        stats = {
            "generation": self.generation,
            "avg_fitness": float(np.mean(fitness_scores)),
            "best_fitness": float(np.max(fitness_scores)),
            "survival_rate": float(sum(1 for org in self.population if org.alive) / self.pop_size),
            "avg_age": float(np.mean([org.age for org in self.population]))
        }
        self.history.append(stats)
        print(f"📊 Stats G{self.generation}: Avg Fitness={stats['avg_fitness']:.2f} | Best={stats['best_fitness']:.2f}")

    def evolve(self):
        self.population.sort(key=lambda x: x.fitness, reverse=True)
        elites = self.population[:self.pop_size // 5]
        new_pop = []
        for e in elites:
            new_pop.append(Organism(e.dna))
        while len(new_pop) < self.pop_size:
            parent = random.choice(elites)
            child_dna = parent.dna + np.random.normal(0, 0.1, parent.dna.shape)
            new_pop.append(Organism(child_dna))
        self.population = new_pop
        self.generation += 1

def main():
    sim = Environment(pop_size=100)
    for i in range(10): # Aumentado para 10 gerações para melhores insights
        sim.run_generation(steps=50)
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_generations": sim.generation - 1,
        "evolution_history": sim.history,
        "status": "Análise de Evolução ATENA Concluída"
    }
    
    os.makedirs("/home/ubuntu/ATENA-/analysis_reports", exist_ok=True)
    with open("/home/ubuntu/ATENA-/analysis_reports/evolution_report.json", "w") as f:
        json.dump(report, f, indent=4)
    
    print("\n🏆 Relatório detalhado gerado em analysis_reports/evolution_report.json")

if __name__ == "__main__":
    main()
