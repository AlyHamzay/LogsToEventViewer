# LogsToEventViewer
Log Forwarder with GUI Configuration, Tray Control, and Event Viewer Integration

A Windows-based log forwarding utility designed for SOC/SIEM teams. This tool monitors both rotating log files (from folders) and static files, forwarding entries to the Windows Event Viewer under specified source names. Key features include:

🔧 GUI Configuration Tool – Setup monitored folders/files, regex patterns, and source names using a user-friendly interface (built with Tkinter).

🔁 Supports Both Rotating and Static Logs – Automatically detects and tails the latest file in a folder or monitors static files directly.

🖥️ Real-Time Viewer – A dashboard-style terminal output showing the latest log per source and pause/resume status.

🟢🔴 System Tray Control – Easily pause or resume forwarding using a system tray app with color status indicators.

📤 Windows Event Log Integration – Forwards all logs to the Application log with the specified event source names.

🔒 Singleton + Admin Guard – Prevents multiple instances and enforces admin privileges for proper Event Viewer access.

🔁 Service Support – Can be registered as a Windows service to auto-start on boot.

📁 Auto Offset Tracking – Remembers log file read positions even after restarts.

⚙️ Fully Configurable via JSON – Behind the scenes, config is stored in a flexible config.json.

Ideal for MSSPs or internal security teams that need lightweight, agentless log forwarding into Windows Event Viewer.


