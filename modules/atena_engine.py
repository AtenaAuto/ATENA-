# atena_engine.py (integração com TaskManager)

from task_manager import (
    TaskManager, TaskType, TaskStatus,
    generate_task_id, is_terminal_status
)

class AtenaCore:
    def __init__(self):
        # ... código existente ...
        self.task_manager = TaskManager()
    
    async def evolve_one_cycle(self) -> Dict:
        """Ciclo de evolução como tarefa"""
        
        # Criar tarefa
        task_id = await self.task_manager.create_task(
            task_type=TaskType.LOCAL_AGENT,
            description=f"Evolution generation {self.generation}",
            priority=8,  # Alta prioridade
            timeout=60000,  # 60s
            max_retries=3,  # Tenta 3 vezes
        )
        
        logger.info(f"[AtenaCore] Iniciando ciclo como tarefa {task_id}")
        
        try:
            # Executa
            await self.task_manager.execute_task(task_id)
            
            # Verifica resultado
            task_info = await self.task_manager.get_task_info(task_id)
            
            if task_info['status'] == TaskStatus.COMPLETED.value:
                logger.info("[AtenaCore] ✅ Ciclo completado com sucesso")
                return {"success": True, "task_id": task_id}
            else:
                logger.error("[AtenaCore] ❌ Ciclo falhou")
                return {
                    "success": False,
                    "task_id": task_id,
                    "error": task_info.get('last_error')
                }
        
        except Exception as e:
            logger.error(f"[AtenaCore] Erro no ciclo: {e}")
            return {"success": False, "error": str(e)}
    
    async def run_autonomous(self, generations: int):
        """Executa múltiplas gerações com TaskManager"""
        
        for gen in range(generations):
            self.generation = gen + 1
            
            # Cada geração é uma tarefa
            result = await self.evolve_one_cycle()
            
            if not result["success"]:
                logger.warning(f"Gerração {gen+1} falhou, retrying...")
                # O retry é automático via TaskManager!
            
            # Status
            self.task_manager.print_status()
