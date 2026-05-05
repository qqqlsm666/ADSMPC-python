# NssMPC/secure_model/utils/param_provider/fss_key_provider.py

import os.path

from ._base_param_provider import BaseParamProvider
from NssMPC.config import DEBUG_LEVEL, DEVICE

class FSSKeyProvider(BaseParamProvider):
    def __init__(self, param_type, saved_name=None, param_tag=None, root_path=None):
        super().__init__(param_type, saved_name, param_tag, root_path)
        self.param = []
        self._key_queue = [] # 使用队列更直观

    def _load_from_disk_fallback(self):
        """
        DEBUG_LEVEL=2 下的兜底：dummy_model 不会再为每个 call site 生成"按形状定制"的 FSS key。
        改为从 gen_params 阶段保存的文件中读出一个 multi-key 包，作为单 key 复用，配合 LookUp.eval / DPF.eval 中的
        DEBUG_LEVEL 分支自动广播到所需输入大小。
        """
        from NssMPC.config.runtime import PartyRuntime
        try:
            party_id = PartyRuntime.party.party_id
        except Exception:
            party_id = 0
        file_name = f"{self.saved_name}_{party_id}.pth"
        file_path = os.path.join(self.root_path, file_name)
        if os.path.exists(file_path):
            self.param = [self.param_type.load(file_path=file_path)]
            return True
        return False

    def load_params(self):
        if not isinstance(self.param, list):
            raise TypeError(f"{self.param_type.__name__} provider expects a list of keys.")

        if not self.param and DEBUG_LEVEL == 2:
            self._load_from_disk_fallback()

        self._key_queue = self.param.copy()
        print(f"Loaded {len(self._key_queue)} key objects for {self.param_type.__name__}")

    def get_parameters(self, num_elements: int):
        """
        从队列的头部获取下一个FSS密钥。
        """
        if not self._key_queue:
            if DEBUG_LEVEL == 2:
                # DEBUG_LEVEL=2: 单 key 复用，无需弹出，直接返回 param[0]
                if not self.param:
                    self._load_from_disk_fallback()
                if not self.param:
                    raise IndexError(
                        f"Ran out of FSS key objects for {self.param_type.__name__} "
                        f"and no on-disk fallback found at {self.root_path}."
                    )
                return self.param[0][0].to(DEVICE)
            elif DEBUG_LEVEL:
                print(f"Warning: FSS key queue for {self.param_type.__name__} is empty. Re-loading for DEBUG.")
                self.load_params() # 在DEBUG模式下重新加载
            else:
                raise IndexError(f"Ran out of FSS key objects for {self.param_type.__name__}")

        if DEBUG_LEVEL == 2:
            # DEBUG_LEVEL=2: 不弹出，固定复用 param[0] 的单 key
            return self.param[0][0].to(DEVICE)

        key_to_return = self._key_queue.pop(0)

        if len(key_to_return) != num_elements:
            raise ValueError(
                f"FSS Key size mismatch for {self.param_type.__name__}. "
                f"Requested: {num_elements}, but the pre-generated key has size: {len(key_to_return)}. "
                "Ensure dummy_model and inference run on the same shapes."
            )

        return key_to_return