#!/usr/bin/env python3
"""
atena_advanced_portfolio_optimizer.py

Um módulo avançado para otimização de portfólio financeiro usando:
- Algoritmo Genético para seleção de ativos
- Simulação de Monte Carlo para análise de risco
- Fronteira Eficiente de Markowitz
- Índice de Sharpe como função de fitness

Autor: ATENA Ω - Geração 346
"""

import numpy as np
import scipy.optimize as sco
import matplotlib.pyplot as plt
import json
import os


class PortfolioOptimizer:
    """
    Classe para otimização de portfólio usando métodos avançados:
    Monte Carlo, Algoritmo Genético, Fronteira Eficiente e Sharpe Ratio.
    """

    def __init__(self, returns_mean, cov_matrix, tickers, risk_free_rate=0.02):
        """
        Inicializa o otimizador com dados dos ativos.

        Parâmetros:
        -----------
        returns_mean : np.ndarray
            Vetor com retorno anual esperado de cada ativo.
        cov_matrix : np.ndarray
            Matriz de covariância dos retornos anuais.
        tickers : list[str]
            Lista com os nomes dos ativos.
        risk_free_rate : float
            Taxa livre de risco anual (default 0.02).
        """
        if len(returns_mean) != len(tickers):
            raise ValueError("Tamanho de returns_mean e tickers deve ser igual")
        if cov_matrix.shape[0] != cov_matrix.shape[1] or cov_matrix.shape[0] != len(tickers):
            raise ValueError("Covariance matrix deve ser quadrada com dimensão igual ao número de ativos")
        self.returns_mean = np.array(returns_mean)
        self.cov_matrix = np.array(cov_matrix)
        self.tickers = tickers
        self.n_assets = len(tickers)
        self.risk_free_rate = risk_free_rate

    def sharpe_ratio(self, returns, risk, risk_free=None):
        """
        Calcula o índice de Sharpe.

        Parâmetros:
        -----------
        returns : float ou np.ndarray
            Retorno esperado do portfólio.
        risk : float ou np.ndarray
            Volatilidade (risco) do portfólio.
        risk_free : float ou None
            Taxa livre de risco anual. Usa o parâmetro da classe se None.

        Retorna:
        --------
        sharpe : float ou np.ndarray
            Índice de Sharpe calculado.
        """
        if risk_free is None:
            risk_free = self.risk_free_rate
        # Previne divisão por zero
        risk = np.maximum(risk, 1e-10)
        return (returns - risk_free) / risk

    def monte_carlo_simulation(self, n_portfolios=5000, random_seed=42):
        """
        Gera portfólios aleatórios e calcula retorno, risco e Sharpe.

        Parâmetros:
        -----------
        n_portfolios : int
            Número de portfólios aleatórios a serem simulados.
        random_seed : int
            Semente para reprodutibilidade.

        Retorna:
        --------
        results : dict
            Dicionário com arrays: 'returns', 'risks', 'sharpe_ratios', 'weights'
        """
        np.random.seed(random_seed)
        results = {
            'returns': np.zeros(n_portfolios),
            'risks': np.zeros(n_portfolios),
            'sharpe_ratios': np.zeros(n_portfolios),
            'weights': np.zeros((n_portfolios, self.n_assets))
        }

        for i in range(n_portfolios):
            weights = np.random.random(self.n_assets)
            weights /= np.sum(weights)
            port_return = np.dot(weights, self.returns_mean)
            port_risk = np.sqrt(weights.T @ self.cov_matrix @ weights)
            sharpe = self.sharpe_ratio(port_return, port_risk)

            results['returns'][i] = port_return
            results['risks'][i] = port_risk
            results['sharpe_ratios'][i] = sharpe
            results['weights'][i, :] = weights

        return results

    def efficient_frontier(self, points=100):
        """
        Calcula a fronteira eficiente e plota o gráfico.

        Parâmetros:
        -----------
        points : int
            Número de pontos na fronteira eficiente.

        Retorna:
        --------
        frontier_returns : np.ndarray
            Retornos esperados da fronteira eficiente.
        frontier_risks : np.ndarray
            Volatilidades correspondentes da fronteira eficiente.
        frontier_weights : np.ndarray
            Pesos dos portfólios na fronteira eficiente.
        """
        def portfolio_volatility(weights):
            return np.sqrt(weights.T @ self.cov_matrix @ weights)

        frontier_returns = np.linspace(np.min(self.returns_mean), np.max(self.returns_mean), points)
        frontier_risks = np.zeros(points)
        frontier_weights = np.zeros((points, self.n_assets))

        # Restrição: soma dos pesos = 1
        constraints = ({'type': 'eq', 'fun': lambda w: np.sum(w) - 1})
        bounds = tuple((0, 1) for _ in range(self.n_assets))

        for i, target_return in enumerate(frontier_returns):
            # Restrição adicional: retorno esperado = target_return
            constraints_target = (
                constraints,
                {'type': 'eq', 'fun': lambda w, target=target_return: np.dot(w, self.returns_mean) - target}
            )

            result = sco.minimize(portfolio_volatility,
                                  x0=np.repeat(1 / self.n_assets, self.n_assets),
                                  bounds=bounds,
                                  constraints=constraints_target,
                                  method='SLSQP')
            if not result.success:
                frontier_risks[i] = np.nan
                frontier_weights[i, :] = np.nan
            else:
                frontier_risks[i] = result.fun
                frontier_weights[i, :] = result.x

        # Plot da fronteira eficiente
        plt.figure(figsize=(10, 6))
        plt.plot(frontier_risks, frontier_returns, 'b--', label='Fronteira Eficiente')
        plt.xlabel('Volatilidade (Risco)')
        plt.ylabel('Retorno Esperado')
        plt.title('Fronteira Eficiente de Markowitz')
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.show()

        return frontier_returns, frontier_risks, frontier_weights

    def genetic_algorithm_optimize(self, generations=50, population_size=100, tournament_size=5,
                                   crossover_prob=0.8, mutation_prob=0.2, mutation_scale=0.05,
                                   random_seed=42):
        """
        Executa um algoritmo genético para otimização do portfólio baseado no índice de Sharpe.

        Parâmetros:
        -----------
        generations : int
            Número de gerações do AG.
        population_size : int
            Número de indivíduos na população.
        tournament_size : int
            Tamanho do torneio para seleção.
        crossover_prob : float
            Probabilidade de crossover.
        mutation_prob : float
            Probabilidade de mutação.
        mutation_scale : float
            Desvio padrão da mutação gaussiana.
        random_seed : int
            Semente para reprodutibilidade.

        Retorna:
        --------
        best_individual : dict
            Dicionário com 'weights', 'return', 'risk', 'sharpe'.
        history : list
            Lista dos melhores índices de Sharpe por geração.
        """
        np.random.seed(random_seed)

        def initialize_population():
            pop = np.random.rand(population_size, self.n_assets)
            pop /= pop.sum(axis=1)[:, None]
            return pop

        def fitness(weights):
            port_return = np.dot(weights, self.returns_mean)
            port_risk = np.sqrt(weights.T @ self.cov_matrix @ weights)
            return self.sharpe_ratio(port_return, port_risk)

        def tournament_selection(population, fitnesses):
            selected = []
            for _ in range(population_size):
                aspirants_idx = np.random.choice(population_size, tournament_size, replace=False)
                aspirants_fitness = fitnesses[aspirants_idx]
                winner_idx = aspirants_idx[np.argmax(aspirants_fitness)]
                selected.append(population[winner_idx])
            return np.array(selected)

        def crossover(parent1, parent2):
            if np.random.rand() < crossover_prob:
                alpha = np.random.rand()
                child1 = alpha * parent1 + (1 - alpha) * parent2
                child2 = alpha * parent2 + (1 - alpha) * parent1
                # Normalizar para soma 1
                child1 /= np.sum(child1)
                child2 /= np.sum(child2)
                return child1, child2
            else:
                return parent1.copy(), parent2.copy()

        def mutate(individual):
            if np.random.rand() < mutation_prob:
                mutation = np.random.normal(0, mutation_scale, self.n_assets)
                mutated = individual + mutation
                mutated = np.clip(mutated, 0, None)
                if mutated.sum() == 0:
                    mutated = individual  # evita vetor zero
                else:
                    mutated /= np.sum(mutated)
                return mutated
            else:
                return individual

        population = initialize_population()
        history = []
        best_individual = None
        best_fitness = -np.inf

        for gen in range(generations):
            fitnesses = np.array([fitness(ind) for ind in population])
            # Armazenar melhor indivíduo da geração
            gen_best_idx = np.argmax(fitnesses)
            gen_best_fit = fitnesses[gen_best_idx]
            if gen_best_fit > best_fitness:
                best_fitness = gen_best_fit
                best_individual = population[gen_best_idx].copy()

            history.append(best_fitness)

            # Seleção
            selected = tournament_selection(population, fitnesses)

            # Criação da próxima geração
            next_generation = []
            for i in range(0, population_size, 2):
                parent1 = selected[i]
                if i + 1 < population_size:
                    parent2 = selected[i + 1]
                else:
                    parent2 = selected[0]
                child1, child2 = crossover(parent1, parent2)
                child1 = mutate(child1)
                child2 = mutate(child2)
                next_generation.append(child1)
                next_generation.append(child2)
            population = np.array(next_generation)[:population_size]

        # Calcular métricas do melhor indivíduo
        best_return = np.dot(best_individual, self.returns_mean)
        best_risk = np.sqrt(best_individual.T @ self.cov_matrix @ best_individual)
        best_sharpe = self.sharpe_ratio(best_return, best_risk)

        # Plot evolução do fitness
        plt.figure(figsize=(10, 5))
        plt.plot(history, label='Melhor Índice de Sharpe')
        plt.xlabel('Geração')
        plt.ylabel('Índice de Sharpe')
        plt.title('Evolução do AG')
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.show()

        return {
            'weights': best_individual,
            'return': best_return,
            'risk': best_risk,
            'sharpe': best_sharpe
        }, history


def main():
    # Dados sintéticos dos ativos (PETR4, VALE3, ITUB4, BBDC4, ABEV3, WEGE3)
    # Retorno anual médio e volatilidade anual realistas para o mercado brasileiro (aproximados)
    # Fonte: estimativas baseadas em dados públicos históricos e literatura
    tickers = ['PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3', 'WEGE3']
    returns_mean = np.array([0.12, 0.13, 0.11, 0.10, 0.09, 0.14])  # retornos anuais estimados
    volatilities = np.array([0.30, 0.35, 0.25, 0.28, 0.22, 0.20])  # volatilidades anuais estimadas

    # Matriz de correlação aproximada (simulada para exemplo)
    corr_matrix = np.array([
        [1.00, 0.65, 0.50, 0.45, 0.40, 0.35],
        [0.65, 1.00, 0.55, 0.50, 0.45, 0.40],
        [0.50, 0.55, 1.00, 0.60, 0.50, 0.45],
        [0.45, 0.50, 0.60, 1.00, 0.55, 0.50],
        [0.40, 0.45, 0.50, 0.55, 1.00, 0.60],
        [0.35, 0.40, 0.45, 0.50, 0.60, 1.00]
    ])

    # Construir matriz de covariância
    cov_matrix = np.outer(volatilities, volatilities) * corr_matrix

    optimizer = PortfolioOptimizer(returns_mean, cov_matrix, tickers)

    # Execução do Monte Carlo
    mc_results = optimizer.monte_carlo_simulation(n_portfolios=5000)

    # Executar algoritmo genético para otimização
    best_portfolio, history = optimizer.genetic_algorithm_optimize(generations=50)

    # Calcular fronteira eficiente para visualização
    frontier_returns, frontier_risks, frontier_weights = optimizer.efficient_frontier(points=100)

    # Relatório final
    print("\n=== Relatório Final de Otimização de Portfólio ===")
    print("Ativos:", tickers)
    print("\nPortfólio Ótimo Encontrado pelo Algoritmo Genético:")
    for ticker, weight in zip(tickers, best_portfolio['weights']):
        print(f"  {ticker}: {weight:.4f}")
    print(f"Retorno Esperado Anual: {best_portfolio['return']:.4f}")
    print(f"Volatilidade Anual: {best_portfolio['risk']:.4f}")
    print(f"Índice de Sharpe: {best_portfolio['sharpe']:.4f}")

    # Melhor portfólio encontrado na simulação Monte Carlo
    mc_best_idx = np.argmax(mc_results['sharpe_ratios'])
    mc_best_weights = mc_results['weights'][mc_best_idx]
    mc_best_return = mc_results['returns'][mc_best_idx]
    mc_best_risk = mc_results['risks'][mc_best_idx]
    mc_best_sharpe = mc_results['sharpe_ratios'][mc_best_idx]

    print("\nMelhor Portfólio Encontrado pela Simulação Monte Carlo:")
    for ticker, weight in zip(tickers, mc_best_weights):
        print(f"  {ticker}: {weight:.4f}")
    print(f"Retorno Esperado Anual: {mc_best_return:.4f}")
    print(f"Volatilidade Anual: {mc_best_risk:.4f}")
    print(f"Índice de Sharpe: {mc_best_sharpe:.4f}")

    # Salvar resultados em JSON
    results_dir = 'atena_evolution'
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    results_path = os.path.join(results_dir, 'portfolio_optimization_results.json')

    results_to_save = {
        'tickers': tickers,
        'monte_carlo': {
            'best_sharpe': float(mc_best_sharpe),
            'best_return': float(mc_best_return),
            'best_volatility': float(mc_best_risk),
            'best_weights': mc_best_weights.tolist()
        },
        'genetic_algorithm': {
            'best_sharpe': float(best_portfolio['sharpe']),
            'best_return': float(best_portfolio['return']),
            'best_volatility': float(best_portfolio['risk']),
            'best_weights': best_portfolio['weights'].tolist(),
            'fitness_history': history
        },
        'frontier': {
            'returns': frontier_returns.tolist(),
            'volatilities': frontier_risks.tolist(),
            'weights': frontier_weights.tolist()
        }
    }

    with open(results_path, 'w') as f:
        json.dump(results_to_save, f, indent=4)

    print(f"\nResultados salvos em: {results_path}")

    # Testes inline básicos para verificação de funcionamento
    print("\nExecutando testes unitários básicos...")

    # Teste Sharpe Ratio
    test_return = 0.15
    test_risk = 0.25
    test_sharpe = optimizer.sharpe_ratio(test_return, test_risk)
    assert np.isclose(test_sharpe, (0.15 - 0.02) / 0.25), "Erro no cálculo do Sharpe Ratio"

    # Teste soma dos pesos AG
    assert np.isclose(np.sum(best_portfolio['weights']), 1.0), "Pesos do portfólio AG não somam 1"

    # Teste soma dos pesos MC
    assert np.allclose(np.sum(mc_results['weights'], axis=1), 1.0), "Pesos dos portfólios MC não somam 1"

    # Teste fronteira eficiente - valores não nan
    assert not np.any(np.isnan(frontier_returns)), "Fronteira eficiente retornos contém NaN"
    assert not np.any(np.isnan(frontier_risks)), "Fronteira eficiente riscos contém NaN"

    print("Todos os testes básicos passaram com sucesso.")


if __name__ == '__main__':
    main()