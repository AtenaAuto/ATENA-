import os
import shutil
from pathlib import Path
from .base import BaseActuator

class FileActuator(BaseActuator):
    """Manipulao de arquivos e diretrios."""
    def __init__(self, sysaware=None, safe_mode=True):
        self.safe_mode = safe_mode
        self._protected_paths = {Path.home(), Path("/"), Path("/etc"), Path("/usr")} if safe_mode else set()
        super().__init__(sysaware)

    def _check_dependencies(self):
        # Sem dependncias externas
        pass

    def _is_safe_path(self, path: Path) -> bool:
        """Verifica se o caminho  seguro para manipulao."""
        if not self.safe_mode:
            return True
        path = Path(path).resolve()
        for protected in self._protected_paths:
            if path == protected or protected in path.parents:
                return False
        return True

    def read_file(self, filepath: str) -> str:
        """L contedo de um arquivo."""
        path = Path(filepath).resolve()
        if not self._is_safe_path(path):
            raise PermissionError(f"Caminho protegido: {path}")
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def write_file(self, filepath: str, content: str, mode='w'):
        """Escreve em um arquivo."""
        path = Path(filepath).resolve()
        if not self._is_safe_path(path):
            raise PermissionError(f"Caminho protegido: {path}")
        with open(path, mode, encoding='utf-8') as f:
            f.write(content)
        self.log_action("write_file", {"path": str(path)})

    def move_file(self, src: str, dst: str):
        """Move/renomeia arquivo."""
        src_path = Path(src).resolve()
        dst_path = Path(dst).resolve()
        if not (self._is_safe_path(src_path) and self._is_safe_path(dst_path)):
            raise PermissionError("Caminho protegido envolvido.")
        shutil.move(str(src_path), str(dst_path))
        self.log_action("move_file", {"src": str(src_path), "dst": str(dst_path)})

    def delete_file(self, filepath: str):
        """Remove arquivo."""
        path = Path(filepath).resolve()
        if not self._is_safe_path(path):
            raise PermissionError(f"Caminho protegido: {path}")
        os.remove(path)
        self.log_action("delete_file", {"path": str(path)})

    def create_directory(self, path: str):
        """Cria diretrio (incluindo pais)."""
        path = Path(path).resolve()
        if not self._is_safe_path(path):
            raise PermissionError(f"Caminho protegido: {path}")
        path.mkdir(parents=True, exist_ok=True)
        self.log_action("create_directory", {"path": str(path)})
