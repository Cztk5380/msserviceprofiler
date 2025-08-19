from test.st.executor.exec_command import CommandExecutor


class ExecParse(CommandExecutor):
    def __init__(self):
        super().__init__()
        self.input_path = ""
        self.output_path = ""
        self.params = []

    def set_input_path(self, input_path):
        self.input_path = input_path

    def set_output_path(self, output_path):
        self.output_path = output_path

    def add_param(self, param_str):
        self.params.append(param_str)

    def ready_go(self):
        # 执行
        self.set_command(
            f'python -m ms_service_profiler.parse --input-path={self.input_path} \
                --output-path={self.output_path} {" ".join(self.params)}'
        )

        self.execute()

        exit_code, _ = self.wait(timeout=600) # 等个10分钟，解析不完直接自杀
        print("wait result: ", exit_code)
        return exit_code == 0
