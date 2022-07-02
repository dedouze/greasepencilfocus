This is the Greasepencil focus addon for Blender to help work faster with multiple GP objects and multiple layers with repeating actions

This project is still in development, but is already working.

## To donate and support my work
https://tipeee.com/dedouze

## demo 
Demo of the first beta version (not updated with the new features):
https://www.youtube.com/watch?v=I56sLzDFHVc

## installation
Required version of Blender :
- Blender 3.1 or newer

Steps :
- Select "code" and download as zip file on your computer
- In Blender top menu, Edit > Preferences > Add-ons, click on "Install" in the top bar
- Browse and select the "greasepencilfocus.zip" file
- Activate the addon with the checkbox. The addon now works automatically with all yout Grease Pencil objects
- Use crt + shift + F to invoke the popup. The shortcut can be changed in the Editt > Preferences > Add-ons panel

## features

- For each layer in a Grease Pencil object, the latest tool/brush and material is saved and reactivated each time you select this layer
- brush size is saved for each GP object
- In the popup, you can switch directly to other GP objects in the "All" tab
- Stroke placement (origin, surface, etc) is saved for each GP object
- In the popup, the "auto save view" option enables saving of the current camera position in the viewport for each GP object. Switching between GP objects changes the camera position to the last position for the selected object. It is better to disable this when playing the scene in loop in the viewport while drawing

## current limitations
- When creating a material from the traditional menu, the new material is not saved directly in the current layer. Click again on the current brush tool to auto-save it with the new material
- If the settings are not saved correctly, click again on the current tool used to force re-saving
- When renaming a layer, its settings are lost. Click again on the current brush tool to auto-save all settings
