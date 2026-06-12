#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 ATENA Ω - Módulo de Otimização de Energia Inteligente (OEI)
Este módulo simula a otimização de uma rede elétrica urbana usando IA.
"""

import random
import time
import json
from datetime import datetime

class AtenaEnergyOptimizer:
    def __init__(self, city_name="Atena City"):
        self.city_name = city_name
        self.grid_status = "Estável"
        self.renewable_ratio = 0.45  # 45% inicial
        self.load_history = []

    def simulate_grid_load(self):
        """Simula a carga atual da rede elétrica."""
        base_load = 500  # MW
        fluctuation = random.uniform(-50, 150)
        current_load = base_load + fluctuation
        return round(current_load, 2)

    def optimize_resources(self, current_load):
        """
        Lógica de IA da ATENA para otimização:
        Ajusta a distribuição de energia renovável vs fóssil.
        """
        optimization_factor = 1.0
        
        if current_load > 600:
            self.grid_status = "Alta Demanda"
            optimization_factor = 1.2
        elif current_load < 500:
            self.grid_status = "Baixa Demanda"
            optimization_factor = 0.8
        else:
            self.grid_status = "Estável"

        # Simula o aumento da eficiência renovável pela ATENA
        self.renewable_ratio = min(0.95, self.renewable_ratio + (0.01 * random.random()))
        
        saved_carbon = (current_load * self.renewable_ratio) * 0.5  # Toneladas de CO2
        
        return {
            "timestamp": datetime.now().isoformat(),
            "city": self.city_name,
            "load_mw": current_load,
            "status": self.grid_status,
            "renewable_ratio": round(self.renewable_ratio * 100, 2),
            "co2_saved_tons": round(saved_carbon, 2)
        }

    def run_cycle(self, iterations=5):
        print(f"🚀 Iniciando Ciclo de Otimização ATENA para {self.city_name}...")
        results = []
        for i in range(iterations):
            load = self.simulate_grid_load()
            report = self.optimize_resources(load)
            results.append(report)
            print(f"Iteração {i+1}: Carga={report['load_mw']}MW | Status={report['status']} | Renovável={report['renewable_ratio']}%")
            time.sleep(0.5)
        
        return results

if __name__ == "__main__":
    optimizer = AtenaEnergyOptimizer()
    optimizer.run_cycle()
