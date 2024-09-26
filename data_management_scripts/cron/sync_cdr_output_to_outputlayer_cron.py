import os, pidfile, sys
current = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.dirname(current))
import dm_util
#from data_management_scripts import dm_util


# First check if there's an existing sync'ing process running; exit if so.
pid_current = int(os.getpid())
pids = []
for line in os.popen(f'ps aux | grep {__file__}'):
   if 'grep' in line or 'aux' in line or '.log' in line:
      continue
   pid = int(line.split()[1])
   if pid != pid_current:
      print('Sync process already running; exiting.')
      sys.exit(0)

# Run sync
dm_util.util.sync_cdr_prospectivity_outputs_to_outputlayer()