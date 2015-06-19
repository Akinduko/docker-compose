from __future__ import unicode_literals
from __future__ import absolute_import
from collections import namedtuple
import os

import docker.errors
import retrying
import six


Volume = namedtuple('Volume', 'path mode host')


def retry_on_api_error(exception):
    return isinstance(
        exception,
        (docker.errors.APIError, docker.errors.DockerException)
    )


api_retry = retrying.retry(
    stop_max_attempt_number=os.environ.get('FIG_API_RETRY_COUNT', 5),
    wait_exponential_multiplier=os.environ.get('FIG_API_RETRY_MULTIPLIER', 500),
    retry_on_exception=retry_on_api_error)


class Container(object):
    """
    Represents a Docker container, constructed from the output of
    GET /containers/:id:/json.
    """
    def __init__(self, client, dictionary, has_been_inspected=False):
        self.client = client
        self.dictionary = dictionary
        self.has_been_inspected = has_been_inspected

    @classmethod
    def from_ps(cls, client, dictionary, **kwargs):
        """
        Construct a container object from the output of GET /containers/json.
        """
        new_dictionary = {
            'Id': dictionary['Id'],
            'Image': dictionary['Image'],
        }
        for name in dictionary.get('Names', []):
            if len(name.split('/')) == 2:
                new_dictionary['Name'] = name
        return cls(client, new_dictionary, **kwargs)

    @classmethod
    def from_id(cls, client, id):
        return cls(client, client.inspect_container(id))

    @classmethod
    def create(cls, client, **options):
        response = client.create_container(**options)
        return cls.from_id(client, response['Id'])

    @classmethod
    def create_with_name(cls, client, name=None, **options):
        response = client.create_container(name=name, **options)
        dictionary = {
            'Name': '/' + name,
            'Image': options.get('image'),
            'Id': response['Id'],
        }
        return cls(client, dictionary)

    @property
    def id(self):
        return self.dictionary['Id']

    @property
    def image(self):
        return self.dictionary['Image']

    @property
    def short_id(self):
        return self.id[:10]

    @property
    def name(self):
        return self.dictionary['Name'][1:]

    @property
    def name_without_project(self):
        return '_'.join(self.dictionary['Name'].split('_')[1:])

    @property
    def number(self):
        try:
            return int(self.name.split('_')[-1])
        except ValueError:
            return None

    @property
    def ports(self):
        return self.get('NetworkSettings.Ports') or {}

    @property
    def human_readable_ports(self):
        def format_port(private, public):
            if not public:
                return private
            return '{HostIp}:{HostPort}->{private}'.format(
                private=private, **public[0])

        return ', '.join(format_port(*item)
                         for item in sorted(six.iteritems(self.ports)))

    @property
    def human_readable_state(self):
        if self.is_running:
            return 'Ghost' if self.get('State.Ghost') else 'Up'
        else:
            return 'Exit %s' % self.get('State.ExitCode')

    @property
    def human_readable_command(self):
        entrypoint = self.get('Config.Entrypoint') or []
        cmd = self.get('Config.Cmd') or []
        return ' '.join(entrypoint + cmd)

    @property
    def environment(self):
        return dict(var.split("=", 1) for var in self.get('Config.Env') or [])

    @property
    def is_running(self):
        return self.get('State.Running')

    @property
    def volumes(self):
        def get_mode(is_rw):
            if is_rw is None:
                return ''
            return 'rw' if is_rw else 'ro'

        def get_volume(volume_item):
            path, host = volume_item
            return Volume(path, get_mode(self.get('VolumesRW').get(path)), host)

        return map(get_volume, six.iteritems(self.get('Volumes')))

    def get(self, key):
        """Return a value from the container or None if the value is not set.

        :param key: a string using dotted notation for nested dictionary
                    lookups
        """
        self.inspect_if_not_inspected()

        def get_value(dictionary, key):
            return (dictionary or {}).get(key)

        return reduce(get_value, key.split('.'), self.dictionary)

    def get_local_port(self, port, protocol='tcp'):
        port = self.ports.get("%s/%s" % (port, protocol))
        return "{HostIp}:{HostPort}".format(**port[0]) if port else None

    @api_retry
    def start(self, **options):
        return self.client.start(self.id, **options)

    @api_retry
    def stop(self, **options):
        return self.client.stop(self.id, **options)

    @api_retry
    def kill(self, **options):
        return self.client.kill(self.id, **options)

    def restart(self):
        return self.client.restart(self.id)

    @api_retry
    def remove(self, **options):
        return self.client.remove_container(self.id, **options)

    def inspect_if_not_inspected(self):
        if not self.has_been_inspected:
            self.inspect()

    def wait(self):
        return self.client.wait(self.id)

    def logs(self, *args, **kwargs):
        return self.client.logs(self.id, *args, **kwargs)

    def inspect(self):
        self.dictionary = self.client.inspect_container(self.id)
        self.has_been_inspected = True
        return self.dictionary

    # TODO: this is only used by tests, should move to a module under tests/
    def links(self):
        links = []
        for container in self.client.containers():
            for name in container['Names']:
                bits = name.split('/')
                if len(bits) > 2 and bits[1] == self.name:
                    links.append(bits[2])
        return links

    def attach(self, *args, **kwargs):
        return self.client.attach(self.id, *args, **kwargs)

    def attach_socket(self, **kwargs):
        return self.client.attach_socket(self.id, **kwargs)

    def __repr__(self):
        return '<Container: %s>' % self.name

    def __eq__(self, other):
        if type(self) != type(other):
            return False
        return self.id == other.id
