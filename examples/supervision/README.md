# Operator-installed supervision

These are templates, not installed services. Replace every `REPLACE_WITH_...`
value with an absolute path or the non-root runtime owner. Keep the state and
logs private and outside imported source. Use the `factory` executable from the
runtime's virtual environment. Provision Git, Docker and the approved images
before starting a worker. Docker must be available after login/reboot.

The Linux unit runs the worker as a non-root user and restarts a failed process.
The macOS plist is a user LaunchAgent and runs after the operator logs in.
Administrator authorization and installation into a service directory are
separate operator actions. No installer writes outside this pack.

Use `factory pause PROJECT_ID` before stopping a service for maintenance. The
worker drains active bounded work on SIGTERM; a hard interruption is recovered
with journal cleanup, expired leases and fresh fencing when it starts again.
Check `factory status` and `factory report` after restart. An accepted or
cancelled project is never automatically restarted as implementation work.

Actual killed-worker recovery is tested. OS service installation, machine reboot
and availability of Docker after reboot still require platform acceptance.
