; One-click installer for 2i. No questions: it installs for the current user (no
; administrator needed), makes a Start menu and Desktop shortcut, and opens 2i.
; Her writing is kept in the app's own data folder (%APPDATA%\2i), which neither
; updating nor uninstalling touches.
Unicode true
!ifndef VERSION
  !define VERSION "0.0.0"
!endif
!ifndef SOURCE_DIR
  !error "pass -DSOURCE_DIR=<the unpacked app folder>"
!endif
!ifndef OUTFILE
  !define OUTFILE "2i-Setup-${VERSION}.exe"
!endif
!define APP "2i"
!define UNINSTKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\2i"

!include "MUI2.nsh"
Name "${APP}"
OutFile "${OUTFILE}"
InstallDir "$LOCALAPPDATA\Programs\2i"
RequestExecutionLevel user
SetCompressor /SOLID lzma
BrandingText "Rearview Foresight"
VIProductVersion "${VERSION}.0"
VIAddVersionKey "ProductName" "2i"
VIAddVersionKey "FileDescription" "2i installer"
VIAddVersionKey "CompanyName" "Rearview Foresight"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "ProductVersion" "${VERSION}"

!define MUI_INSTFILESPAGE_FINISHHEADER_TEXT "2i is installed"
!define MUI_INSTFILESPAGE_FINISHHEADER_SUBTEXT "Opening it now."
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Section "Install"
  SetAutoClose true
  SetOutPath "$INSTDIR"
  File /r "${SOURCE_DIR}\*.*"
  WriteUninstaller "$INSTDIR\Uninstall 2i.exe"
  CreateShortcut "$SMPROGRAMS\2i.lnk" "$INSTDIR\2i.exe"
  CreateShortcut "$DESKTOP\2i.lnk" "$INSTDIR\2i.exe"
  WriteRegStr HKCU "${UNINSTKEY}" "DisplayName" "2i"
  WriteRegStr HKCU "${UNINSTKEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${UNINSTKEY}" "Publisher" "Rearview Foresight"
  WriteRegStr HKCU "${UNINSTKEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTKEY}" "DisplayIcon" "$INSTDIR\2i.exe"
  WriteRegStr HKCU "${UNINSTKEY}" "UninstallString" '"$INSTDIR\Uninstall 2i.exe"'
  WriteRegDWORD HKCU "${UNINSTKEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTKEY}" "NoRepair" 1
SectionEnd

Function .onInstSuccess
  Exec '"$INSTDIR\2i.exe"'
FunctionEnd

Section "Uninstall"
  Delete "$SMPROGRAMS\2i.lnk"
  Delete "$DESKTOP\2i.lnk"
  DeleteRegKey HKCU "${UNINSTKEY}"
  ; $INSTDIR here is the folder this uninstaller sits in.
  RMDir /r "$INSTDIR"
SectionEnd
