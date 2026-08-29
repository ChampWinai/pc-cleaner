"""Plugin system for PC Cleaner extensibility."""
import logging
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Any, Callable, Optional
import json

log = logging.getLogger(__name__)

PLUGINS_DIR = Path(__file__).parent / 'plugins'
USER_PLUGINS_DIR = Path.home() / '.pccleaner' / 'plugins'


class PluginInterface:
    """Base interface for PC Cleaner plugins."""

    metadata = {
        'name': 'Unknown Plugin',
        'version': '0.0.0',
        'author': 'Unknown',
        'description': 'A PC Cleaner plugin',
        'enabled': True,
    }

    def on_init(self):
        """Called when plugin is loaded."""
        pass

    def on_shutdown(self):
        """Called when plugin is unloaded."""
        pass

    def register_hooks(self) -> Dict[str, Callable]:
        """
        Return dict of hook_name -> callable.
        Possible hooks:
        - 'scan_<category>': Custom scan function
        - 'clean_<category>': Custom clean function
        - 'on_scan_complete': Called after any scan
        - 'on_clean_complete': Called after any clean
        - 'ui_menu_items': Return list of UI menu items to add
        """
        return {}

    def register_categories(self) -> List[Dict[str, Any]]:
        """
        Return list of new categories to add to the scanner.
        Each category should have: name, display_name, icon
        """
        return []


class PluginManager:
    """Manages plugin loading and lifecycle."""

    def __init__(self):
        self.plugins: Dict[str, PluginInterface] = {}
        self.hooks: Dict[str, List[Callable]] = {}
        self.enabled_plugins = set()

    def discover_plugins(self) -> List[Path]:
        """Find all available plugins."""
        plugins = []
        for plugin_dir in [PLUGINS_DIR, USER_PLUGINS_DIR]:
            if plugin_dir.exists():
                for item in plugin_dir.iterdir():
                    if item.is_dir() and not item.name.startswith('_'):
                        plugin_file = item / 'plugin.py'
                        if plugin_file.exists():
                            plugins.append(plugin_file)
        return plugins

    def load_plugin(self, plugin_path: Path) -> Optional[str]:
        """
        Load a plugin from file.
        Returns plugin name on success, None on failure.
        """
        try:
            plugin_name = plugin_path.parent.name
            spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
            if not spec or not spec.loader:
                log.error(f"Failed to create spec for {plugin_name}")
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[plugin_name] = module
            spec.loader.exec_module(module)

            if not hasattr(module, 'Plugin') or not issubclass(module.Plugin, PluginInterface):
                log.error(f"Plugin {plugin_name} does not define Plugin class")
                return None

            plugin = module.Plugin()

            if not plugin.metadata.get('enabled', True):
                log.info(f"Plugin {plugin_name} is disabled")
                return None

            plugin.on_init()
            self.plugins[plugin_name] = plugin
            self.enabled_plugins.add(plugin_name)

            # Register hooks
            hooks = plugin.register_hooks()
            for hook_name, callback in hooks.items():
                if hook_name not in self.hooks:
                    self.hooks[hook_name] = []
                self.hooks[hook_name].append(callback)

            log.info(f"Plugin loaded: {plugin_name} v{plugin.metadata.get('version', '?')}")
            return plugin_name

        except Exception as e:
            log.error(f"Failed to load plugin from {plugin_path}: {e}", exc_info=True)
            return None

    def load_all_plugins(self):
        """Discover and load all available plugins."""
        plugins = self.discover_plugins()
        loaded = 0
        for plugin_path in plugins:
            if self.load_plugin(plugin_path):
                loaded += 1
        log.info(f"Loaded {loaded}/{len(plugins)} plugins")

    def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a plugin."""
        try:
            if plugin_name in self.plugins:
                plugin = self.plugins[plugin_name]
                plugin.on_shutdown()

                # Remove hooks
                for hook_list in self.hooks.values():
                    for i, hook in enumerate(hook_list):
                        if hook.__self__ is plugin:
                            hook_list.pop(i)

                del self.plugins[plugin_name]
                self.enabled_plugins.discard(plugin_name)
                log.info(f"Plugin unloaded: {plugin_name}")
                return True
        except Exception as e:
            log.error(f"Failed to unload plugin {plugin_name}: {e}")
        return False

    def get_plugin(self, plugin_name: str) -> Optional[PluginInterface]:
        """Get a loaded plugin by name."""
        return self.plugins.get(plugin_name)

    def call_hook(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """
        Call all callbacks registered for a hook.
        Returns list of results.
        """
        results = []
        if hook_name in self.hooks:
            for callback in self.hooks[hook_name]:
                try:
                    result = callback(*args, **kwargs)
                    results.append(result)
                except Exception as e:
                    log.error(f"Error in hook {hook_name}: {e}", exc_info=True)
        return results

    def get_custom_categories(self) -> List[Dict[str, Any]]:
        """Get all custom categories from plugins."""
        categories = []
        for plugin in self.plugins.values():
            try:
                custom = plugin.register_categories()
                categories.extend(custom)
            except Exception as e:
                log.error(f"Error getting categories from {plugin}: {e}")
        return categories

    def get_enabled_plugins(self) -> List[Dict[str, Any]]:
        """Get list of enabled plugins with metadata."""
        return [
            {
                'name': name,
                'metadata': plugin.metadata,
                'hooks': list(self.hooks.keys()),
            }
            for name, plugin in self.plugins.items()
        ]


def create_example_plugin():
    """Create an example plugin for users to reference."""
    example_dir = USER_PLUGINS_DIR / 'example-plugin'
    example_dir.mkdir(parents=True, exist_ok=True)

    plugin_file = example_dir / 'plugin.py'
    if not plugin_file.exists():
        plugin_file.write_text('''"""Example PC Cleaner plugin."""
from operation_context import PluginInterface

class Plugin(PluginInterface):
    metadata = {
        'name': 'Example Plugin',
        'version': '1.0.0',
        'author': 'Your Name',
        'description': 'An example plugin showing how to extend PC Cleaner',
        'enabled': True,
    }

    def on_init(self):
        print("Example plugin loaded!")

    def register_hooks(self):
        return {
            'on_scan_complete': self.on_scan_complete,
        }

    def on_scan_complete(self, results):
        print(f"Scan completed: {results}")
''')
        log.info(f"Example plugin created at {example_dir}")


# Global plugin manager instance
plugin_manager = PluginManager()
