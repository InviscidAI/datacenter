import os
import subprocess
import logging
import threading

import jinja2
from jinja2 import select_autoescape
from openai import OpenAI
from llama_index.core import SimpleDirectoryReader
from pathlib import Path

STARTUP_FINISHED = 'Application startup complete.'


def _drain_logs(pipe):
    for _ in pipe:
        pass


class ChatBot:
    def __init__(self,  model_name, schema, openai_api_key='EMPTY', port=8000):
        self.model_name = model_name

        self.server_proc = None

        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(Path(os.path.dirname(__file__)) / 'templates'),
            autoescape=select_autoescape()
        )
        self.messages = []
        self.render_system_message(schema)

        self.logger = None

        self.openai_api_key = openai_api_key
        self.port = port
        self.openai_api_base = f'http://localhost:{port}/v1'

        self.missing_message = False

    def render_system_message(self, schema):
        template = self.jinja_env.get_template('system_message_template.jinja')
        rendered = template.render(schema=schema)
        self.messages.append({'role': 'system', 'content': rendered})

    def file_upload(self, *, directory=None, content_dict=None):
        if self.missing_message:
            raise ValueError('Missing a client message that must be returned.')
        # filenames parameter will be ignored if content_dict is set
        if content_dict is None:
            if dir is None:
                raise ValueError('Either content_dict or directory should be provided.')
            content_dict = {}
            reader = SimpleDirectoryReader(directory)
            docs = reader.load_data()

            for doc in docs:
                content_dict[doc.metadata['file_name']] = doc.text

        template = self.jinja_env.get_template('file_upload_template.jinja')
        rendered = template.render(files=content_dict)
        self.messages.append({'role': 'system', 'content': rendered})

    def send_user_message(self, message, stream=False):
        if self.missing_message:
            raise ValueError('Missing a client message that must be returned.')
        self.messages.append({'role': 'user', 'content': message})

        client = OpenAI(
            api_key=self.openai_api_key,
            base_url=self.openai_api_base,
        )

        response = client.chat.completions.create(
            model=self.model_name,
            messages=self.messages,
            temperature=0.2,
            stream=stream
        )

        if stream:
            self.missing_message = True
            return response
        else:
            assistant_reply = response.choices[0].message.content
            self.messages.append({'role': 'assistant', 'content': assistant_reply})
            return assistant_reply

    def return_full_message(self, message):
        self.messages.append({'role': 'assistant', 'content': message})
        self.missing_message = False

    def start_server(self, **kwargs):
        cmd = [
            'vllm', 'serve', str(self.model_name),
            '--api-key', str(self.openai_api_key),
            '--port', str(self.port),
        ]

        for key, value in kwargs.items():
            cmd.append('--' + key)
            cmd.append(str(value))

        self.server_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        for line in self.server_proc.stdout:
            print(line, end='')
            if STARTUP_FINISHED in str(line):
                break

        t = threading.Thread(target=_drain_logs,
                             args=(self.server_proc.stdout,),
                             daemon=True)
        t.start()

    def stop_server(self):
        if self.server_proc is not None:
            self.server_proc.kill()
            self.server_proc = None
        else:
            raise ValueError('Cannot stop server that has not been started')
