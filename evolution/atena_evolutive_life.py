#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 ATENA Ω - Simulador de Vida Artificial Evolutiva (SVAE)
Um sistema complexo onde organismos digitais evoluem através de algoritmos genéticos
e pequenas redes neurais para sobreviver em um ambiente hostil.
"""

import numpy as np
import random
import json
import os
from datetime import datetime

class Organism:
    def __init__(self, dna=None):
        # DNA define os pesos da rede neural (4 inputs, 2 outputs)
        # Inputs: [Distância Comida, Energia Atual, Velocidade Atual, Idade]
        # Outputs: [Aceleração, Rotação]
        if dna is None:
            self.dna = np.random.uniform(-1, 1, (4, 2))
        else:
            self.dna = dna
        
        self.energy = 100.0
        self.age = 0
        self.fitness = 0
        self.alive = True

    def think(self, inputs):
        """Processa inputs através da rede neural baseada no DNA."""
        inputs = np.array(inputs)
        outputs = np.tanh(np.dot(inputs, self.dna))
        return outputs

    def update(self, inputs):
        if not self.alive:
            return
        
        outputs = self.think(inputs)
        accel, rotate = outputs
        
        # Consumo de energia baseado no movimento
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
        self.food_positions = np.random.uniform(0, 100, (20, 2))

    def run_generation(self, steps=100):
        print(f"🧬 Geração {self.generation} em curso...")
        for _ in range(steps):
            for org in self.population:
                if org.alive:
                    # Simula inputs (distâncias fictícias para o teste)
                    dist_food = random.random() * 10
                    inputs = [dist_food, org.energy/100.0, 0.5, org.age/100.0]
                    org.update(inputs)
                    
                    # Simula encontrar comida
                    if random.random() < 0.05:
                        org.energy = min(100, org.energy + 20)
                        org.fitness += 5

        # Avalia fitness e evolui
        self.evolve()

    def evolve(self):
        # Seleciona os melhores
        self.population.sort(key=lambda x: x.fitness, reverse=True)
        elites = self.population[:self.pop_size // 5]
        
        new_pop = []
        # Elitismo
        for e in elites:
            new_pop.append(Organism(e.dna))
        
        # Reprodução com mutação
        while len(new_pop) < self.pop_size:
            parent = random.choice(elites)
            child_dna = parent.dna + np.random.normal(0, 0.1, parent.dna.shape)
            new_pop.append(Organism(child_dna))
            
        self.population = new_pop
        self.generation += 1
        
        best_fitness = elites[0].fitness
        print(f"✅ Evolução Concluída. Melhor Fitness: {best_fitness:.2f}")

def main():
    sim = Environment(pop_size=100)
    for i in range(5):
        sim.run_generation(steps=50)
    
    # Salva o estado final
    report = {
        "timestamp": datetime.now().isoformat(),
        "final_generation": sim.generation,
        "best_fitness": max(o.fitness for o in sim.population),
        "status": "Missão de Evolução AGI Concluída"
    }
    
    os.makedirs("/home/ubuntu/ATENA-/analysis_reports", exist_ok=True)
    with open("/home/ubuntu/ATENA-/analysis_reports/evolution_report.json", "w") as f:
        json.dump(report, f, indent=4)
    
    print("\n🏆 Relatório de Evolução gerado com sucesso.")

if __name__ == "__main__":
    main()
