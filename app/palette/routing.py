from akiri.framework.route import Router

from .about import AboutApplication, SupportApplication, AutoUpdateApplication
from .backup import BackupRestoreApplication
from .environment import EnvironmentApplication
from .gcs import GCSApplication
from .general import GeneralApplication
from .manage import ManageApplication
from .monitor import MonitorApplication
from .profile import ProfileApplication
from .setup import SetupApplication
from .server import ServerApplication
from .s3 import S3Application
from .user import UserApplication
from .yml import YmlApplication
from .workbooks import WorkbookApplication

class RestRouter(Router):

    def __init__(self):
        super(RestRouter, self).__init__()
        self.add_route(r'/about\Z', AboutApplication())
        self.add_route(r'/backup\Z', BackupRestoreApplication())
        self.add_route(r'/environment\Z', EnvironmentApplication())
        self.add_route(r'/gcs\Z', GCSApplication())
        self.add_route(r'/general\Z|/general/', GeneralApplication())
        self.add_route(r'/manage\Z', ManageApplication())
        self.add_route(r'/monitor\Z', MonitorApplication())
        self.add_route(r'/profile\Z', ProfileApplication())
        self.add_route(r'/s3\Z', S3Application())
        self.add_route(r'/setup\Z|/setup/', SetupApplication())
        self.add_route(r'/servers?(/(?P<action>[^\s]+))?\Z',
                       ServerApplication())
        self.add_route(r'/support\Z', SupportApplication())
        self.add_route(r'/update\Z', AutoUpdateApplication())
        self.add_route(r'/users?(/(?P<action>[^\s]+))?\Z',
                       UserApplication())
        self.add_route(r'/yml\Z', YmlApplication())
        self.add_route(r'/workbooks?(/(?P<action>[^\s]+))?\Z',
                       WorkbookApplication())


from .setup import SetupConfigPage
from .general import GeneralPage
from .server import ServerConfigPage
from .user import UserConfigPage
from .yml import YmlPage

class ConfigureRouter(Router):

    def __init__(self):
        super(ConfigureRouter, self).__init__()
        self.add_route(r'/setup\Z', SetupConfigPage())
        self.add_route(r'/general\Z', GeneralPage())
        self.add_route(r'/servers?\Z', ServerConfigPage())
        self.add_route(r'/users?\Z', UserConfigPage())
        self.add_route(r'/yml\Z', YmlPage())
