"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Panel handling for Photoshop

"""
import os
import sys
import webbrowser
import unicodedata

import photoshop

class PanelGenerator(object):
    """
    Panel generation functionality for Photoshop
    """
    def __init__(self, engine):
        self._engine = engine
        self._dialogs = []
        engine_root_dir = self._engine.disk_location

    ##########################################################################################
    # public methods

    def populate_panel(self):
        """
        Render the entire Tank panel.
        """
        # slight hack here but first ensure that the panel is empty
        photoshop.clear_panel()

        # now add the context item on top of the main panel
        self._add_context_buttons()

        # now enumerate all items and create panel objects for them
        panel_items = []
        for (cmd_name, cmd_details) in self._engine.commands.items():
             panel_items.append( AppCommand(cmd_name, cmd_details) )

        self._engine.log_debug("panel_items: %s", panel_items)

        # now add favourites
        for fav in self._engine.get_setting("menu_favourites"):
            app_instance_name = fav["app_instance"]
            panel_name = fav["name"]

            # scan through all panel items
            for cmd in panel_items:
                 if cmd.get_app_instance_name() == app_instance_name and cmd.name == panel_name:
                     # found our match!
                     cmd.add_button()
                     # mark as a favourite item
                     cmd.favourite = True

        # now go through all of the panel items.
        # separate them out into various sections
        commands_by_app = {}

        for cmd in panel_items:
            if cmd.get_type() == "context_menu":
                # context menu!
                cmd.add_button()
            else:
                # normal menu
                app_name = cmd.get_app_name()
                if app_name is None:
                    # un-parented app
                    app_name = "Other Items"
                if not app_name in commands_by_app:
                    commands_by_app[app_name] = []
                commands_by_app[app_name].append(cmd)

        # now add all apps to main panel
        self._add_app_buttons(commands_by_app)

    def destroy_panel(self):
        photoshop.clear_panel()

    ##########################################################################################
    # context panel and UI
    def _add_context_buttons(self):
        """
        Adds a context panel which displays the current context
        """

        #ctx = self._engine.context
        #ctx_name = str(ctx)
        # todo: display context on menu (requires tank core 0.12.7+)

        # create the panel object
        photoshop.add_button("Jump to Shotgun", self._jump_to_sg)
        photoshop.add_button("Jump to File System", self._jump_to_fs)


    def _jump_to_sg(self):
        if self._engine.context.entity is None:
            # project-only!
            url = "%s/detail/%s/%d" % (self._engine.shotgun.base_url,
                                       "Project",
                                       self._engine.context.project["id"])
        else:
            # entity-based
            url = "%s/detail/%s/%d" % (self._engine.shotgun.base_url,
                                       self._engine.context.entity["type"],
                                       self._engine.context.entity["id"])

        # deal with fucked up nuke unicode handling
        if url.__class__ == unicode:
            url = unicodedata.normalize('NFKD', url).encode('ascii', 'ignore')
        webbrowser.open(url, autoraise=True)


    def _jump_to_fs(self):
        """
        Jump from context to FS
        """

        if self._engine.context.entity:
            paths = self._engine.tank.paths_from_entity(self._engine.context.entity["type"],
                                                     self._engine.context.entity["id"])
        else:
            paths = self._engine.tank.paths_from_entity(self._engine.context.project["type"],
                                                     self._engine.context.project["id"])

        # launch one window for each location on disk
        # todo: can we do this in a more elegant way?
        for disk_location in paths:

            # get the setting        
            system = sys.platform
            
            # run the app
            if system == "linux2":
                cmd = 'xdg-open "%s"' % disk_location
            elif system == "darwin":
                cmd = 'open "%s"' % disk_location
            elif system == "win32":
                cmd = 'cmd.exe /C start "Folder" "%s"' % disk_location
            else:
                raise Exception("Platform '%s' is not supported." % system)

            exit_code = os.system(cmd)
            if exit_code != 0:
                self._engine.log_error("Failed to launch '%s'!" % cmd)


    ##########################################################################################
    # app panels
    def _add_app_buttons(self, commands_by_app):
        """
        Add all apps to the main panel, process them one by one.
        """
        for app_name in sorted(commands_by_app.keys()):
            if len(commands_by_app[app_name]) > 1:
                # more than one panel entry fort his app
                # make a sub panel and put all items in the sub panel
                for cmd in commands_by_app[app_name]:
                    cmd.add_button()
            else:
                # this app only has a single entry.
                # display that on the panel
                # todo: Should this be labelled with the name of the app
                # or the name of the panel item? Not sure.
                cmd_obj = commands_by_app[app_name][0]
                if not cmd_obj.favourite:
                    # skip favourites since they are alreay on the panel
                    cmd_obj.add_button()


class AppCommand(object):
    """
    Wraps around a single command that you get from engine.commands
    """
    def __init__(self, name, command_dict):
        self.name = name
        self.properties = command_dict["properties"]
        self.callback = command_dict["callback"]
        self.favourite = False


    def get_app_name(self):
        """
        Returns the name of the app that this command belongs to
        """
        if "app" in self.properties:
            return self.properties["app"].display_name
        return None

    def get_app_instance_name(self):
        """
        Returns the name of the app instance, as defined in the environment.
        Returns None if not found.
        """
        if "app" not in self.properties:
            return None

        app_instance = self.properties["app"]
        engine = app_instance.engine

        for (app_instance_name, app_instance_obj) in engine.apps.items():
            if app_instance_obj == app_instance:
                # found our app!
                return app_instance_name
        return None

    def get_documentation_url_str(self):
        """
        Returns the documentation as a str
        """
        if "app" in self.properties:
            app = self.properties["app"]
            doc_url = app.documentation_url
            # deal with nuke's inability to handle unicode. #fail
            if doc_url.__class__ == unicode:
                doc_url = unicodedata.normalize('NFKD', doc_url).encode('ascii', 'ignore')
            return doc_url

        return None

    def get_type(self):
        """
        returns the command type. Returns node, custom_pane or default
        """
        return self.properties.get("type", "default")

    def add_button(self):
        """
        Adds an app command to the panel
        """
        photoshop.add_button(self.name, self.callback)
