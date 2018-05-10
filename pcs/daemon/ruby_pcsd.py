import json
import os.path
from base64 import b64decode
from collections import namedtuple
from time import time as now

from tornado.gen import Task, multi, convert_yielded
from tornado.web import HTTPError
from tornado.httputil import split_host_and_port, HTTPServerRequest
from tornado.process import Subprocess

from pcs.daemon import log


SINATRA_GUI = "sinatra_gui"
SINATRA_REMOTE = "sinatra_remote"
SYNC_CONFIGS = "sync_configs"

DEFAULT_SYNC_CONFIG_DELAY = 5

class SinatraResult(namedtuple("SinatraResult", "headers, status, body")):
    @classmethod
    def from_response(cls, response):
        return cls(
            response["headers"],
            response["status"],
            b64decode(response["body"])
        )

class Wrapper:
    # pylint: disable=too-many-instance-attributes
    def __init__(
        self, gem_home, pcsd_cmdline_entry, log_file_location,
        debug=False, ruby_executable="ruby", https_proxy=None, no_proxy=None
    ):
        self.__gem_home = gem_home
        self.__pcsd_cmdline_entry = pcsd_cmdline_entry
        self.__pcsd_dir = os.path.dirname(pcsd_cmdline_entry)
        self.__log_file_location = log_file_location
        self.__ruby_executable = ruby_executable
        self.__debug = debug
        self.__https_proxy = https_proxy
        self.__no_proxy = no_proxy

    def get_sinatra_request(self, request: HTTPServerRequest):
        host, port = split_host_and_port(request.host)
        return {"env": {
            "PATH_INFO": request.path,
            "QUERY_STRING": request.query,
            "REMOTE_ADDR": request.remote_ip,
            "REMOTE_HOST": request.host,
            "REQUEST_METHOD": request.method,
            "REQUEST_URI": f"{request.protocol}://{request.host}{request.uri}",
            "SCRIPT_NAME": "",
            "SERVER_NAME": host,
            "SERVER_PORT": port,
            "SERVER_PROTOCOL": request.version,
            "HTTP_HOST": request.host,
            "HTTP_ACCEPT": "*/*",
            "HTTP_COOKIE": ";".join([
                v.OutputString() for v in request.cookies.values()
            ]),
            "HTTPS": "on" if request.protocol == "https" else "off",
            "HTTP_VERSION": request.version,
            "REQUEST_PATH": request.uri,
            "rack.input": request.body.decode("utf8"),
        }}

    async def send_to_ruby(self, request_json):
        env = {
            "GEM_HOME": self.__gem_home,
            "PCSD_DEBUG": "true" if self.__debug else "false"
        }
        if self.__no_proxy is not None:
            env["NO_PROXY"] = self.__no_proxy
        if self.__https_proxy is not None:
            env["HTTPS_PROXY"] = self.__https_proxy

        pcsd_ruby = Subprocess(
            [
                self.__ruby_executable, "-I",
                self.__pcsd_dir,
                self.__pcsd_cmdline_entry
            ],
            stdin=Subprocess.STREAM,
            stdout=Subprocess.STREAM,
            stderr=Subprocess.STREAM,
            env=env
        )
        await Task(pcsd_ruby.stdin.write, str.encode(request_json))
        pcsd_ruby.stdin.close()
        return await multi([
            Task(pcsd_ruby.stdout.read_until_close),
            Task(pcsd_ruby.stderr.read_until_close),
        ])

    async def run_ruby(self, request_type, request=None):
        request = request or {}
        request.update({
            "type": request_type,
            "config": {
                "log_location": self.__log_file_location,
            },
        })
        request_json = json.dumps(request)
        stdout, stderr = await self.send_to_ruby(request_json)
        try:
            return json.loads(stdout)
        except Exception as e:
            message_list = [f"Cannot decode json from ruby pcsd wrapper: '{e}'"]
            if self.__debug:
                message_list.extend([
                    f"Request for ruby pcsd wrapper: '{request_json}'",
                    f"Response stdout from ruby pcsd wrapper: '{stdout}'",
                    f"Response stderr from ruby pcsd wrapper: '{stderr}'",
                ])
            for message in message_list:
                log.pcsd.error(message)
            raise HTTPError(500)

    async def request_gui(
        self, request: HTTPServerRequest, user, groups, is_authenticated
    ) -> SinatraResult:
        sinatra_request = self.get_sinatra_request(request)
        # Sessions handling was removed from ruby. However, some session
        # information is needed for ruby code (e.g. rendering some parts of
        # templates). So this information must be sent to ruby by another way.
        sinatra_request.update({
            "session": {
                "username": user,
                "groups": groups,
                "is_authenticated": is_authenticated,
            }
        })
        response = await convert_yielded(self.run_ruby(
            SINATRA_GUI,
            sinatra_request
        ))
        return SinatraResult.from_response(response)

    async def request_remote(self, request: HTTPServerRequest) -> SinatraResult:
        response = await convert_yielded(self.run_ruby(
            SINATRA_REMOTE,
            self.get_sinatra_request(request)
        ))
        return SinatraResult.from_response(response)

    async def sync_configs(self):
        try:
            response = await convert_yielded(self.run_ruby(SYNC_CONFIGS))
            return response["next"]
        except HTTPError:
            log.pcsd.error("Config synchronization failed")
            return int(now()) + DEFAULT_SYNC_CONFIG_DELAY
