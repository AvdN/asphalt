import asyncio
from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from typing import Dict, Any, Union

from typeguard import check_argument_types

from asphalt.core.context import Context
from asphalt.core.util import PluginContainer, merge_config

__all__ = ('Component', 'ContainerComponent')


class Component(metaclass=ABCMeta):
    """This is the base class for all Asphalt components."""

    __slots__ = ()

    @abstractmethod
    async def start(self, ctx: Context):
        """
        Perform any necessary tasks to start the services provided by this component.

        Components typically use the context to:
          * publish resources (:meth:`~asphalt.core.context.Context.publish_resource` and
            :meth:`~asphalt.core.context.Context.publish_lazy_resource`)
          * request resources (:meth:`~asphalt.core.context.Context.request_resource`)

        It is advisable for Components to first publish all the resources they can before
        requesting any. This will speed up the dependency resolution and prevent deadlocks.

        :param ctx: the containing context for this component
        """


class ContainerComponent(Component):
    """
    A component that can contain other components.

    This class is essential to building nontrivial applications.
    """

    __slots__ = 'child_components', 'component_config'

    def __init__(self, components: Dict[str, Any]=None):
        self.child_components = OrderedDict()
        self.component_config = components or {}

    def add_component(self, alias: str, type: Union[str, type]=None, **kwargs):
        """
        Add a child component.

        This will instantiate a component class, as specified by the ``type`` argument.

        If the second argument is omitted, the value of ``alias`` is used as its value.

        The locally given configuration can be overridden by component configuration parameters
        supplied to the constructor (the ``components`` argument).

        When configuration values are provided both as keyword arguments to this method and
        component configuration through the ``components`` constructor argument, the configurations
        are merged together using :func:`~asphalt.core.util.merge_config` in a way that the
        configuration values from the ``components`` argument override the keyword arguments to
        this method.

        :param alias: a name for the component instance, unique within this container
        :param type: entry point name or :class:`Component` subclass or a textual reference to one

        """
        assert check_argument_types()
        if not isinstance(alias, str) or not alias:
            raise TypeError('component_alias must be a nonempty string')
        if alias in self.child_components:
            raise ValueError('there is already a child component named "{}"'.format(alias))

        # Allow the external configuration to override the constructor arguments
        kwargs = merge_config(kwargs, self.component_config.get(alias, {}))

        component = component_types.create_object(type or alias, **kwargs)
        self.child_components[alias] = component

    async def start(self, ctx: Context):
        """
        Create child components that have been configured but not yet created and then calls their
        :meth:`~Component.start` methods in separate tasks and waits until they have completed.

        """
        for alias in self.component_config:
            if alias not in self.child_components:
                self.add_component(alias)

        if self.child_components:
            tasks = []
            for component in self.child_components.values():
                retval = component.start(ctx)
                if retval is not None:
                    tasks.append(retval)

            if tasks:
                await asyncio.gather(*tasks)


component_types = PluginContainer('asphalt.components', Component)
