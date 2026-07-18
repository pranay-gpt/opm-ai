# OPM Flow Reference

Complete run-command and option reference for the OPM Flow reservoir simulator as
installed on this machine. Intended as the source-of-truth for building a wrapper.

- Binary: `/usr/bin/flow`
- Version: `flow 2026.04` (`flow --version`)
- Platform: Ubuntu 24.04 (noble), arm64
- MPI: Open MPI 4.1.6 (`/usr/bin/mpirun`)
- Standard help (`flow --help`): 217 options
- Full help (`flow --help-all`): 283 options (adds hidden / deprecated / VTK / seconds-based time controls)

Installed OPM packages:

```
libopm-common          2026.04-1~noble   Eclipse file tools (library)
libopm-common-bin      2026.04-1~noble   Eclipse file tools (utilities)
libopm-grid            2026.04-1~noble   DUNE grid implementations (library)
libopm-grid-bin        2026.04-1~noble   corner-point grid utilities
libopm-simulators      2026.04-1~noble   reservoir simulators (library)
libopm-simulators-bin  2026.04-1~noble   simulator applications (flow)
python3-opm-common     2026.04-1~noble   Python wrappers (import opm)
python3-opm-simulators 2026.04-1~noble   Python wrappers for simulators
```

---

## 1. Invocation

```bash
# Serial run, deck given positionally
flow [OPTIONS] CASE.DATA

# Deck given by option (equivalent)
flow [OPTIONS] --ecl-deck-file-name=CASE.DATA

# Parallel run over N MPI ranks
mpirun -np N flow [OPTIONS] CASE.DATA

# Options loaded from an .ini parameter file
flow --parameter-file=params.ini CASE.DATA

# OpenMP threads per MPI rank
flow --threads-per-process=4 CASE.DATA

# Combined MPI + OpenMP
mpirun -np 4 flow --threads-per-process=2 CASE.DATA
```

Key facts:

- There is exactly one binary: `flow`. No separate `flow_blackoil` / `flow_gaswater`
  / `flow_onephase` executables are installed. Physics (black-oil, gas-water,
  thermal, CO2STORE, etc.) is auto-detected from the deck keywords.
- The positional argument is the ECL deck, usually `CASE.DATA`. It can appear
  before or after options.
- Every option has the form `--long-name=VALUE`. There are **no short flags**
  except `-h` / `--help`.
- Booleans require an explicit value: `--enable-vtk-output=true` (a bare
  `--enable-vtk-output` will not work).
- VALUE types: `BOOLEAN` (`true`/`false`), `INTEGER`, `SCALAR` (float), `STRING`.
- Unknown options cause flow to error out. Validate wrapper input against the
  help dump for the installed version.
- Diagnostics are written to `CASE.PRT` and `CASE.DBG` in the output directory.
  Exit code is nonzero on failure.

### Help / meta options

```bash
flow -h                 # or --help : print standard option list and exit
flow --help             # same
flow --help-all         # print ALL parameters incl. obsolete/hidden/deprecated
flow --version          # print version (flow 2026.04)
```

---

## 2. Most-used options (quick reference)

```bash
# Choose output directory (created if needed)
flow --output-dir=results CASE.DATA

# Validate the deck without simulating (parse + config check only)
flow --enable-dry-run=true CASE.DATA

# Turn on VTK output (needs the global switch AND per-field switches)
flow --enable-vtk-output=true --vtk-write-pressures=true CASE.DATA

# Run in parallel with a specific partitioner
mpirun -np 8 flow --partition-method=zoltanwell CASE.DATA

# Pick a linear solver / GPU acceleration
flow --linear-solver=cprw CASE.DATA
flow --accelerator-mode=cusparse --gpu-device-id=0 CASE.DATA

# Restart handling
flow --load-step=0 CASE.DATA          # load last stored report step from .OPMRST
flow --save-step=all CASE.DATA        # serialize every report step

# Control terminal chatter and parameter echo
flow --output-mode=log --print-parameters=0 CASE.DATA

# Relax deck parsing (use with care)
flow --parsing-strictness=low CASE.DATA
```

---

## 3. Option catalog (standard `--help`, 217 options)

All defaults are as reported by `flow --help` for version 2026.04.

### 3.1 Input / deck parsing

| Option | Type | Default | Description |
|---|---|---|---|
| `--ecl-deck-file-name` | STRING | `""` | Name of the file containing the ECL deck to simulate. |
| `--parameter-file` | STRING | `""` | An `.ini` file with a set of run-time parameters. |
| `--ignore-keywords` | STRING | `""` | List of Eclipse keywords to ignore, `:`-separated. |
| `--parsing-strictness` | STRING | `normal` | `normal` (stop for critical errors), `high` (stop for all errors), `low` (do not stop on unsupported keywords even if critical). |
| `--action-parsing-strictness` | STRING | `normal` | ActionX/PyAction parsing: `normal` or `low`. |
| `--input-skip-mode` | STRING | `100` | SKIP100/SKIP300 compatibility: `100`, `300`, or `all`. |

### 3.2 Output / reporting

| Option | Type | Default | Description |
|---|---|---|---|
| `--output-dir` | STRING | `""` | Directory for result files. |
| `--output-mode` | STRING | `all` | Which messages print: `none`, `log`, `all`. |
| `--output-interval` | INTEGER | `1` | Report steps between restart-data writes. |
| `--print-parameters` | INTEGER | `2` | Print run-time parameter values at start. |
| `--enable-ecl-output` | BOOLEAN | `true` | Write binary output compatible with commercial Eclipse. |
| `--enable-esmry` | BOOLEAN | `true` | Write ESMRY file for fast summary loading. |
| `--ecl-output-interval` | INTEGER | `-1` | Report steps skipped between ECL result writes. |
| `--ecl-output-double-precision` | BOOLEAN | `false` | Use double precision in output (for 'perfect' restarts). |
| `--enable-async-ecl-output` | BOOLEAN | `true` | Write ECL results non-blocking (separate thread). |
| `--enable-write-all-solutions` | BOOLEAN | `false` | Write all solutions, not only report steps. |
| `--enable-opm-rst-file` | BOOLEAN | `false` | Include OPM-specific keywords in ECL restart file. |
| `--enable-terminal-output` | BOOLEAN | `true` | Print progress to terminal. |
| `--enable-logging-fallout-warning` | BOOLEAN | `false` | Developer: report logging on non-root ranks. |
| `--debug-verbosity-level` | INTEGER | `1` | Debug verbosity in `.DBG` file (0 disables most). |
| `--force-disable-fluid-in-place-output` | BOOLEAN | `false` | Do not print fluid-in-place after each report step. |
| `--force-disable-resv-fluid-in-place-output` | BOOLEAN | `false` | Do not print reservoir-volume values. |
| `--output-extra-convergence-info` | STRING | `none` | Extra convergence files: `none`, `steps` (INFOSTEP), `iterations` (INFOITER), or comma-combined. |

### 3.3 Run mode

| Option | Type | Default | Description |
|---|---|---|---|
| `--enable-dry-run` | STRING | `auto` | Actually run (`false`), only pretend (`true`), or `auto`. Use `true` to validate a deck. |

### 3.4 Time stepping (days-based, standard help)

| Option | Type | Default | Description |
|---|---|---|---|
| `--enable-adaptive-time-stepping` | BOOLEAN | `true` | Adaptive time stepping between report steps. |
| `--initial-time-step-in-days` | SCALAR | `1` | Size of the initial time step (days). |
| `--solver-max-time-step-in-days` | SCALAR | `365` | Maximum time step size (days). |
| `--solver-min-time-step` | SCALAR | `1e-12` | Minimum time step (days field/metric, hours lab). |
| `--full-time-step-initially` | BOOLEAN | `false` | Always attempt a report step in a single substep. |
| `--time-step-after-event-in-days` | SCALAR | `-1` | Step size of first step after an event (days). |
| `--min-time-step-based-on-newton-iterations` | SCALAR | `0` | Min step from Newton iteration counts. |
| `--min-time-step-before-shutting-problematic-wells-in-days` | SCALAR | `0.01` | Min step below which problematic wells are not shut. |
| `--time-step-control` | STRING | `pid+newtoniteration` | `pid`, `pid+iteration`, `pid+newtoniteration`, `iterationcount`, `newtoniterationcount`, `general3rdorder`, `hardcoded`. |
| `--time-step-control-tolerance` | SCALAR | `0.1` | Tolerance used by the time-step control algorithm. |
| `--time-step-control-target-iterations` | INTEGER | `30` | Target linear iterations for step control. |
| `--time-step-control-target-newton-iterations` | INTEGER | `8` | Target Newton iterations for step control. |
| `--time-step-control-decay-rate` | SCALAR | `0.75` | Step-size decay rate when target exceeded. |
| `--time-step-control-growth-rate` | SCALAR | `1.25` | Step-size growth rate when target undercut. |
| `--time-step-control-decay-damping-factor` | SCALAR | `1` | Decay damping when target iterations exceeded. |
| `--time-step-control-growth-damping-factor` | SCALAR | `3.2` | Growth damping when target iterations undercut. |
| `--time-step-control-file-name` | STRING | `timesteps` | File with hardcoded time-step sizes. |
| `--time-step-control-parameters` | STRING | `0.125;0.25;0.125;0.75;0.25` | 3rd-order controller `beta_1;beta_2;beta_3;alpha_2;alpha_3`. |
| `--time-step-control-safety-factor` | SCALAR | `0.8` | Safety factor multiplying the control tolerance. |
| `--time-step-control-max-reduction-time-step` | SCALAR | `0.1` | 3rd-order: reject if relative step change exceeds this. |
| `--time-step-control-reject-completed-step` | BOOLEAN | `false` | 3rd-order: allow rejecting completed steps. |
| `--time-step-control-tolerance-test-version` | STRING | `standard` | 3rd-order: `standard` or `control-error-filtering`. |
| `--time-step-verbosity` | INTEGER | `1` | Chattiness during time integration. |
| `--enable-tuning` | BOOLEAN | `false` | Honor some aspects of the TUNING keyword. |

### 3.5 Nonlinear (Newton / NLDD) solver

| Option | Type | Default | Description |
|---|---|---|---|
| `--nonlinear-solver` | STRING | `newton` | `newton` or `nldd`. |
| `--newton-max-iterations` | INTEGER | `20` | Max Newton iterations per time step. |
| `--newton-min-iterations` | INTEGER | `2` | Min Newton iterations per time step. |
| `--newton-max-relax` | SCALAR | `0.5` | Max relaxation factor of a Newton iteration. |
| `--newton-relaxation-type` | STRING | `dampen` | `dampen` or `sor`. |
| `--use-update-stabilization` | BOOLEAN | `true` | Detect/correct oscillation or stagnation in Newton. |
| `--solver-verbosity` | INTEGER | `1` | Chattiness of the non-linear solver. |
| `--max-residual-allowed` | SCALAR | `1e+07` | Absolute max residual before cutting time step. |
| `--min-strict-cnv-iter` | INTEGER | `-1` | Min Newton iters before relaxed CNV tolerance. |
| `--min-strict-mb-iter` | INTEGER | `-1` | Min Newton iters before relaxed MB tolerance. |
| `--relaxed-max-pv-fraction` | SCALAR | `0.03` | Pore-volume fraction where CNV may be violated. |
| `--pri-var-oscilation-threshold` | SCALAR | `1e-05` | Threshold for primary-variable switching. |
| `--project-saturations` | BOOLEAN | `false` | Do saturation projection. |
| `--use-implicit-ipr` | BOOLEAN | `true` | Compute implicit IPR for stability checks. |

#### NLDD (nonlinear domain decomposition) sub-options

| Option | Type | Default | Description |
|---|---|---|---|
| `--num-local-domains` | INTEGER | `0` | Number of local domains for NLDD. |
| `--local-solve-approach` | STRING | `gauss-seidel` | `jacobi` or `gauss-seidel`. |
| `--max-local-solve-iterations` | INTEGER | `20` | Max iterations for local solves. |
| `--local-tolerance-scaling-cnv` | SCALAR | `0.1` | Stricter CNV tolerance scaling for local solves. |
| `--local-tolerance-scaling-mb` | SCALAR | `1` | Stricter MB tolerance scaling for local solves. |
| `--local-domains-ordering-measure` | STRING | `maxpressure` | `maxpressure`, `averagepressure`, `residual`. |
| `--local-domains-partitioning-method` | STRING | `zoltan` | `zoltan`, `simple`, or `*.partition` file. |
| `--local-domains-partitioning-imbalance` | SCALAR | `1.03` | Subdomain partitioning imbalance tolerance. |
| `--local-domains-partition-well-neighbor-levels` | INTEGER | `1` | Neighbor levels around wells kept in same domain. |
| `--nldd-local-linear-solver` | STRING | `ilu0` | `ilu0`, `dilu`, `cpr_quasiimpes`, `amg`, or `.json`. |
| `--nldd-local-linear-solver-max-iter` | INTEGER | `200` | Max iterations of the NLDD local linear solver. |
| `--nldd-local-linear-solver-reduction` | SCALAR | `0.01` | Min residual reduction for NLDD local solver. |
| `--nldd-num-initial-newton-iter` | INTEGER | `1` | Initial global Newton iterations when running NLDD. |
| `--nldd-relative-mobility-change-tol` | SCALAR | `0.1` | Single-cell relative mobility change threshold. |
| `--local-well-solve-control-switching` | BOOLEAN | `true` | Allow control switching during local well solves. |

### 3.6 Linear solver

| Option | Type | Default | Description |
|---|---|---|---|
| `--linear-solver` | STRING | `cprw` | `cprw`, `ilu0`, `dilu`, `cpr` (alias for cprw), `cpr_quasiimpes`, `cpr_trueimpes`, `cpr_trueimpesanalytic`, `amg`, `hybrid`, or a `.json` file. |
| `--linear-solver-accelerator` | STRING | `cpu` | Backend: `cpu` or `gpu`. |
| `--linear-solver-max-iter` | INTEGER | `200` | Max linear solver iterations. |
| `--linear-solver-reduction` | SCALAR | `0.01` | Min residual reduction the solver must achieve. |
| `--linear-solver-restart` | INTEGER | `40` | Iterations after which GMRES restarts. |
| `--linear-solver-verbosity` | INTEGER | `0` | Verbosity (0 off, 2 all). |
| `--linear-solver-ignore-convergence-failure` | BOOLEAN | `false` | Continue as if nothing happened on non-convergence. |
| `--linear-solver-print-json-definition` | BOOLEAN | `true` | Write JSON solver definition to DBG file. |
| `--relaxed-linear-solver-reduction` | SCALAR | `0.01` | Min reduction for a solution to be accepted. |
| `--use-gmres` | BOOLEAN | `false` | Use GMRES as the linear solver. |
| `--scale-linear-system` | BOOLEAN | `false` | Scale linear system by equation/variable type. |
| `--matrix-add-well-contributions` | BOOLEAN | `false` | Put well influences into Jacobian/preconditioner. |
| `--max-single-precision-days` | SCALAR | `20` | Max step size where single-precision linear solve is used. |

#### CPR preconditioner

| Option | Type | Default | Description |
|---|---|---|---|
| `--cpr-reuse-setup` | INTEGER | `4` | 0 recreate every solve, 1 every timestep, 2 if >10 iters, 3 never, 4 every CprReuseInterval. |
| `--cpr-reuse-interval` | INTEGER | `30` | Recreate interval when cpr-reuse-setup=4. |
| `--cpr-weights-thread-parallel` | BOOLEAN | `false` | OpenMP parallelize CPR weight calculation. |

#### ILU preconditioner

| Option | Type | Default | Description |
|---|---|---|---|
| `--ilu-fillin-level` | INTEGER | `0` | Fill-in level of the ILU preconditioner. |
| `--ilu-relaxation` | SCALAR | `0.9` | Relaxation factor of the ILU preconditioner. |
| `--ilu-redblack` | BOOLEAN | `false` | Red-black partitioning for ILU. |
| `--ilu-reorder-spheres` | BOOLEAN | `false` | Reorder red-black ILU entries in spheres. |
| `--milu-variant` | STRING | `ilu` | `ilu`, `milu_1`, `milu_2`, `milu_3`, `milu_4`. |

### 3.7 GPU / accelerator

| Option | Type | Default | Description |
|---|---|---|---|
| `--accelerator-mode` | STRING | `none` | `cusparse`, `opencl`, `amgcl`, `rocalution`, `rocsparse`, `none`. |
| `--gpu-device-id` | INTEGER | `0` | Device ID for cusparse/opencl solver. |
| `--gpu-aware-mpi` | BOOLEAN | `false` | Use GPU-direct communication in MPI. |
| `--verify-gpu-aware-mpi` | BOOLEAN | `false` | Fail if GPU-aware MPI unsupported (with gpu-aware-mpi=true). |
| `--opencl-platform-id` | INTEGER | `0` | Platform ID for openclSolver. |
| `--opencl-ilu-parallel` | BOOLEAN | `true` | Parallelize ILU decomposition/application on GPU. |

### 3.8 Parallel / partitioning / load balancing

| Option | Type | Default | Description |
|---|---|---|---|
| `--partition-method` | STRING | `zoltanwell` | `simple`, `zoltan`, `metis`, `zoltanwell`. |
| `--imbalance-tol` | SCALAR | `1.1` | Tolerable load-balancing imbalance. |
| `--edge-weights-method` | STRING | `transmissibility` | `uniform`, `transmissibility`, `logtrans`. |
| `--num-overlap` | INTEGER | `1` | Layers of overlap in parallel partition. |
| `--add-corners` | BOOLEAN | `false` | Add corners to partition. |
| `--owner-cells-first` | BOOLEAN | `true` | Order owned cells before ghost/overlap cells. |
| `--serial-partitioning` | BOOLEAN | `false` | Partition on a single process for parallel runs. |
| `--allow-distributed-wells` | BOOLEAN | `false` | Distribute a well's perforations across processes. |
| `--allow-splitting-inactive-wells` | BOOLEAN | `true` | Split inactive wells across domains. |
| `--metis-params` | STRING | `default` | METIS configuration or `.json` file. |
| `--edge-conformal` | BOOLEAN | `false` | Edge-conformal cornerpoint processing. |
| `--threads-per-process` | INTEGER | `2` | Max OpenMP threads per process (`-1` = automatic). |

### 3.9 Wells

| Option | Type | Default | Description |
|---|---|---|---|
| `--use-multisegment-well` | BOOLEAN | `true` | Use multi-segment well model. |
| `--enable-well-operability-check` | BOOLEAN | `true` | Enable well operability checking. |
| `--enable-well-operability-check-iter` | BOOLEAN | `false` | Operability checking during iterations. |
| `--shut-unsolvable-wells` | BOOLEAN | `true` | Shut unsolvable wells. |
| `--solve-welleq-initially` | BOOLEAN | `true` | Fully solve well equations before each reservoir iteration. |
| `--alternative-well-rate-init` | BOOLEAN | `true` | Alternative well rate initialization. |
| `--max-welleq-iter` | INTEGER | `30` | Max iterations to solve the well equations. |
| `--max-inner-iter-wells` | INTEGER | `50` | Max inner iterations for standard wells. |
| `--max-inner-iter-ms-wells` | INTEGER | `100` | Max inner iterations for multi-segment wells. |
| `--strict-inner-iter-wells` | INTEGER | `40` | Inner well iterations with strict tolerance. |
| `--strict-outer-iter-wells` | INTEGER | `6` | Newton iterations checking wells with strict tolerance. |
| `--max-well-status-switch-for-wells` | INTEGER | `99` | Max stop<->open switches per well per time step. |
| `--max-well-status-switch-in-inner-iter-wells` | INTEGER | `99` | Max stop<->open switches during inner iterations. |
| `--maximum-number-of-well-switches` | INTEGER | `3` | Max times a well switches to the same control. |
| `--maximum-number-of-group-switches` | INTEGER | `3` | Max times a group switches to the same control. |
| `--well-group-constraints-max-iterations` | INTEGER | `1` | Max iterations in well/group switching algorithm. |
| `--check-group-constraints-inner-well-iterations` | BOOLEAN | `true` | Check group constraints during inner well iterations. |
| `--max-newton-iterations-with-inner-well-iterations` | INTEGER | `99` | Max Newton iterations with inner well iterations. |
| `--regularization-factor-wells` | SCALAR | `100` | Regularization factor for wells. |
| `--dwell-fraction-max` | SCALAR | `0.2` | Max absolute change of a well volume fraction per iteration. |
| `--dbhp-max-rel` | SCALAR | `1` | Max relative BHP change per iteration. |
| `--max-pressure-change-ms-wells` | SCALAR | `1e+06` | Max relative pressure change per MSW iteration. |
| `--tolerance-pressure-ms-wells` | SCALAR | `1000` | Tolerance for MSW pressure equations. |
| `--relaxed-pressure-tol-msw` | SCALAR | `10000` | Relaxed MSW pressure tolerance. |
| `--relaxed-well-flow-tol` | SCALAR | `0.001` | Relaxed well flow residual tolerance. |
| `--tolerance-wells` | SCALAR | `0.0001` | Well convergence tolerance. |
| `--tolerance-well-control` | SCALAR | `1e-07` | Tolerance for well control equations. |

#### Injection multiplier / mechanical

| Option | Type | Default | Description |
|---|---|---|---|
| `--inj-mult-osc-threshold` | SCALAR | `0.1` | Injection multiplier oscillation threshold. |
| `--inj-mult-damp-mult` | SCALAR | `0.9` | Injection multiplier dampening factor. |
| `--inj-mult-min-damp-factor` | SCALAR | `0.05` | Minimum injection multiplier dampening factor. |

### 3.10 Network solver

| Option | Type | Default | Description |
|---|---|---|---|
| `--pre-solve-network` | BOOLEAN | `true` | Pre-solve and iterate the network at start-up. |
| `--network-max-outer-iterations` | INTEGER | `3` | Max outer iterations before giving up. |
| `--network-max-strict-outer-iterations` | INTEGER | `10` | Max outer iterations before relaxing tolerance. |
| `--network-max-sub-iterations` | INTEGER | `100` | Max sub-iterations to update network pressures. |
| `--network-max-pressure-update-in-bars` | SCALAR | `5` | Max pressure update in inner network iterations. |
| `--network-pressure-update-damping-factor` | SCALAR | `0.1` | Damping factor in inner network pressure updates. |
| `--nupcol-group-rate-tolerance` | SCALAR | `0.001` | Tolerance for VREP/RAIN group rate changes. |

### 3.11 Convergence tolerances

| Option | Type | Default | Description |
|---|---|---|---|
| `--tolerance-mb` | SCALAR | `1e-07` | Mass-balance error relative to total mass. |
| `--tolerance-mb-relaxed` | SCALAR | `1e-06` | Relaxed mass-balance tolerance. |
| `--tolerance-cnv` | SCALAR | `0.01` | Local convergence tolerance (max local saturation errors). |
| `--tolerance-cnv-relaxed` | SCALAR | `1` | Relaxed local convergence tolerance. |
| `--tolerance-cnv-energy` | SCALAR | `0.4182` | Local energy convergence tolerance. |
| `--tolerance-cnv-energy-relaxed` | SCALAR | `41.82` | Relaxed local energy convergence tolerance. |
| `--tolerance-energy-balance` | SCALAR | `4.182e-06` | Energy balance error relative to total energy. |
| `--tolerance-energy-balance-relaxed` | SCALAR | `4.182e-05` | Relaxed energy balance tolerance. |
| `--tolerance-max-dp` | SCALAR | `0` | Tolerance for max pressure change per Newton iteration (>0 allows convergence regardless of residuals). |
| `--tolerance-max-ds` | SCALAR | `0` | Tolerance for max saturation change per Newton iteration. |
| `--tolerance-max-drs` | SCALAR | `0` | Tolerance for max RS change per Newton iteration. |
| `--tolerance-max-drv` | SCALAR | `0` | Tolerance for max RV change per Newton iteration. |
| `--relaxed-linear-solver-reduction` | SCALAR | `0.01` | (see linear solver) minimum accepted reduction. |

### 3.12 Primary-variable limits / physical bounds

| Option | Type | Default | Description |
|---|---|---|---|
| `--dp-max-rel` | SCALAR | `0.3` | Max relative pressure change per iteration. |
| `--ds-max` | SCALAR | `0.2` | Max absolute saturation change per iteration. |
| `--max-temperature-change` | SCALAR | `5` | Max absolute temperature change per iteration. |
| `--pressure-max` | SCALAR | `1e+99` | Maximum absolute pressure. |
| `--pressure-min` | SCALAR | `-1e+99` | Minimum absolute pressure. |
| `--pressure-scale` | SCALAR | `1` | Scaling of pressure primary variable. |
| `--temperature-max` | SCALAR | `1e+09` | Maximum absolute temperature. |
| `--temperature-min` | SCALAR | `0` | Minimum absolute temperature. |
| `--maximum-water-saturation` | SCALAR | `1` | Maximum water saturation. |
| `--water-only-threshold` | SCALAR | `1` | Water saturation at/above which a cell is water-only. |
| `--update-equations-scaling` | BOOLEAN | `false` | Update mass-balance equation scaling during the run. |

### 3.13 Adaptive-step / solver restart control

| Option | Type | Default | Description |
|---|---|---|---|
| `--continue-on-convergence-error` | BOOLEAN | `false` | Continue with non-converged solution below min step. |
| `--solver-continue-on-convergence-failure` | BOOLEAN | `false` | Continue when min solver step reached. |
| `--solver-max-restarts` | INTEGER | `10` | Max breakdowns before a substep is abandoned. |
| `--solver-restart-factor` | SCALAR | `0.33` | Factor time steps are shortened after restarts. |
| `--solver-growth-factor` | SCALAR | `2` | Factor steps are elongated after a successful substep. |
| `--solver-max-growth` | SCALAR | `3` | Max factor steps are elongated after a report step. |

### 3.14 Physics / model options

| Option | Type | Default | Description |
|---|---|---|---|
| `--conserve-inner-energy-thermal` | BOOLEAN | `false` | Conserve inner energy (not enthalpy) with THERMAL. |
| `--enable-drift-compensation` | BOOLEAN | `false` | Compensate systematic mass losses via next-step source term. |
| `--enable-drift-compensation-temp` | BOOLEAN | `true` | Compensate systematic mass losses in energy equation (TEMP). |
| `--enable-storage-cache` | BOOLEAN | `true` | Store previous storage terms to avoid recomputation. |
| `--check-satfunc-consistency` | BOOLEAN | `true` | Check saturation-function consistency. |
| `--num-satfunc-consistency-sample-points` | INTEGER | `5` | Max reported failures per saturation-function check. |

### 3.15 Restart / serialization

| Option | Type | Default | Description |
|---|---|---|---|
| `--load-step` | INTEGER | `-1` | Load serialized state from `.OPMRST`: a report step, or 0 for last stored. |
| `--save-step` | STRING | `""` | Save serialized state: a step number, `all`, `:x` (every x'th), negative x keeps only last, `last`. |
| `--sched-restart` | BOOLEAN | `false` | On restart, init wells/groups from historical SCHEDULE (not the `.UNRST` well state). Tested with the 7.12 workflow: exit 0. |
| `--enable-opm-rst-file` | BOOLEAN | `false` | (see output) include OPM keywords for OPM restart. |

### 3.16 Hybrid Newton (experimental)

| Option | Type | Default | Description |
|---|---|---|---|
| `--use-hybrid-newton` | BOOLEAN | `false` | Use Hybrid Newton. |
| `--hybrid-newton-config-file` | STRING | `hybridNewtonConfig.json` | JSON config path for Hybrid Newton. |
| `--convergence-monitoring` | BOOLEAN | `false` | Enable convergence monitoring. |
| `--convergence-monitoring-cut-off` | INTEGER | `6` | Cut-off limit for convergence monitoring. |
| `--convergence-monitoring-decay-factor` | SCALAR | `0.75` | Decay factor for convergence monitoring. |

### 3.17 TPSA linear/Newton solver (two-point stencil approximation)

| Option | Type | Default | Description |
|---|---|---|---|
| `--tpsa-linear-solver` | STRING | `ilu0` | `ilu0`, `dilu`, `amg`, `umfpack`, or `.json`. |
| `--tpsa-linear-solver-max-iter` | INTEGER | `200` | Max TPSA linear iterations. |
| `--tpsa-linear-solver-reduction` | SCALAR | `0.001` | Min residual reduction for TPSA convergence. |
| `--tpsa-relaxed-linear-solver-reduction` | SCALAR | `0.001` | Relaxed TPSA reduction (use with care). |
| `--tpsa-linear-solver-restart` | INTEGER | `40` | GMRES restart iterations if tpsa-use-gmres=true. |
| `--tpsa-linear-solver-verbosity` | INTEGER | `0` | TPSA linear solver verbosity (0 off, 2 all). |
| `--tpsa-linear-solver-ignore-convergence-failure` | BOOLEAN | `false` | Continue even if TPSA linear solver did not converge. |
| `--tpsa-linear-solver-print-json-definition` | BOOLEAN | `false` | Print JSON config of the TPSA linear solver. |
| `--tpsa-use-gmres` | BOOLEAN | `false` | Use GMRES (else BiCGStab). |
| `--tpsa-ilu-fillin-level` | INTEGER | `0` | Fill-in level of TPSA ILU preconditioner. |
| `--tpsa-ilu-relaxation` | SCALAR | `0.9` | Relaxation factor for TPSA ILU preconditioner. |
| `--tpsa-newton-max-iterations` | INTEGER | `20` | Max TPSA Newton iterations. |
| `--tpsa-newton-min-iterations` | INTEGER | `1` | Min TPSA Newton iterations. |
| `--tpsa-newton-target-iterations` | INTEGER | `10` | Optimum TPSA Newton iterations. |
| `--tpsa-newton-tolerance` | SCALAR | `0.001` | Max raw error for TPSA convergence. |
| `--tpsa-newton-max-error` | SCALAR | `1e+100` | Max error tolerated by TPSA Newton before abort. |
| `--tpsa-newton-verbosity` | INTEGER | `1` | TPSA Newton verbosity: 0 none, 1 basic, 2 all. |

---

## 4. Additional options exposed only by `--help-all`

These 66 extra options are hidden, deprecated, obsolete, or in seconds-based /
VTK groups. `--help-all` prints 283 options in total.

### 4.1 Time controls in SI seconds (alternatives to the days-based ones)

| Option | Type | Default | Description |
|---|---|---|---|
| `--end-time` | SCALAR | `1e+100` | Simulation end time [s]. |
| `--initial-time-step-size` | SCALAR | `86400` | Initial time step size [s]. |
| `--max-time-step-size` | SCALAR | `inf` | Max size all time steps are limited to [s]. |
| `--min-time-step-size` | SCALAR | `0` | Min size all time steps are limited to [s]. |
| `--max-time-step-divisions` | INTEGER | `10` | Max halvings of the step before bailing out. |
| `--predetermined-time-steps-file` | STRING | `""` | File with predetermined step sizes (one per line). |
| `--restart-time` | SCALAR | `-1e+35` | Simulation time at which a restart is attempted [s]. |
| `--restart-writing-interval` | INTEGER | `16777215` | Frequency of serializing time steps to disk. |

### 4.2 Newton (generic/hidden) variants

| Option | Type | Default | Description |
|---|---|---|---|
| `--newton-tolerance` | SCALAR | `0.01` | Max raw error for a converged solution. |
| `--newton-target-iterations` | INTEGER | `10` | Optimum number of Newton iterations per step. |
| `--newton-max-error` | SCALAR | `1e+100` | Max error tolerated by Newton before abort. |
| `--newton-verbose` | BOOLEAN | (hidden) | Verbose Newton output. |
| `--newton-write-convergence` | BOOLEAN | (hidden) | Write Newton convergence behavior. |

### 4.3 Grid / physics (hidden)

| Option | Type | Default | Description |
|---|---|---|---|
| `--enable-gravity` | BOOLEAN | `true` | Gravity correction for pressure gradients. |
| `--enable-grid-adaptation` | BOOLEAN | `false` | Adaptive grid refinement/coarsening. |
| `--enable-intensive-quantity-cache` | BOOLEAN | `true` | Cache intensive quantities. |
| `--enable-thermodynamic-hints` | BOOLEAN | `false` | Enable thermodynamic hints. |
| `--explicit-rock-compaction` | BOOLEAN | `false` | Use last-step pressure when evaluating rock compaction. |
| `--num-pressure-points-equil` | INTEGER | `2000` | Pressure points per direction in equilibration tables. |
| `--use-average-density-ms-wells` | BOOLEAN | `false` | Approximate segment densities by averaging with outlet. |

### 4.4 Restart / serialization (file-name and coupling variants)

| Option | Type | Default | Description |
|---|---|---|---|
| `--load-file` | STRING | `""` | `.OPMRST` file to load serialized state (default CASENAME.OPMRST). |
| `--save-file` | STRING | `""` | `.OPMRST` file to save serialized state (default CASENAME.OPMRST). |
| `--slave` | BOOLEAN | `false` | Run as slave in a master-slave (reservoir coupling) simulation. |

### 4.5 Partitioning (deprecated / debug)

| Option | Type | Default | Description |
|---|---|---|---|
| `--external-partition` | STRING | `""` | File with an externally generated partitioning of active cells. |
| `--debug-emit-cell-partition` | BOOLEAN | `false` | Emit cell partitions as a debugging aid. |
| `--zoltan-params` | STRING | (default) | Zoltan configuration or `.json` file. |
| `--zoltan-imbalance-tol` | SCALAR | `1.1` | DEPRECATED: use `--imbalance-tol`. |
| `--zoltan-phg-edge-size-threshold` | SCALAR | (default) | Zoltan PHG edge-size threshold. |

### 4.6 VTK output fields

All require the global switch `--enable-vtk-output=true`. Async writing is
controlled by `--enable-async-vtk-output` (default `true`).

Default `true` fields: `--vtk-write-densities`, `--vtk-write-mole-fractions`,
`--vtk-write-porosity`, `--vtk-write-pressures`,
`--vtk-write-relative-permeabilities`, `--vtk-write-saturations`,
`--vtk-write-temperature`.

Default `false` fields (opt-in):

```
--vtk-write-average-molar-masses           --vtk-write-oil-vaporization-factor
--vtk-write-diffusion-coefficients         --vtk-write-potential-gradients
--vtk-write-dof-index                       --vtk-write-primary-vars
--vtk-write-effective-diffusion-coefficients --vtk-write-primary-vars-meaning
--vtk-write-extrusion-factor                --vtk-write-process-rank
--vtk-write-filter-velocities               --vtk-write-saturated-gas-oil-vaporization-factor
--vtk-write-fugacities                      --vtk-write-saturated-oil-gas-dissolution-factor
--vtk-write-fugacity-coeffs                 --vtk-write-saturation-ratios
--vtk-write-gas-dissolution-factor          --vtk-write-tortuosities
--vtk-write-gas-formation-volume-factor     --vtk-write-total-mass-fractions
--vtk-write-gas-saturation-pressure         --vtk-write-total-mole-fractions
--vtk-write-intrinsic-permeabilities        --vtk-write-tracer-concentration
--vtk-write-mass-fractions                  --vtk-write-viscosities
--vtk-write-mobilities                      --vtk-write-water-formation-volume-factor
--vtk-write-molarities                      --vtk-write-oil-formation-volume-factor
--vtk-write-oil-saturation-pressure
```

Field meanings (from `--help-all`):

- `--vtk-write-densities` phase densities
- `--vtk-write-pressures` phase pressures
- `--vtk-write-saturations` phase saturations
- `--vtk-write-temperature` temperature
- `--vtk-write-porosity` porosity
- `--vtk-write-relative-permeabilities` phase relative permeabilities
- `--vtk-write-mobilities` phase mobilities
- `--vtk-write-viscosities` component phase viscosities
- `--vtk-write-mole-fractions` / `--vtk-write-mass-fractions` phase composition
- `--vtk-write-total-mole-fractions` / `--vtk-write-total-mass-fractions` totals
- `--vtk-write-molarities` component molarities
- `--vtk-write-fugacities` / `--vtk-write-fugacity-coeffs` component fugacities
- `--vtk-write-gas-dissolution-factor` R_s of observed oil
- `--vtk-write-oil-vaporization-factor` R_v of observed gas
- `--vtk-write-saturated-oil-gas-dissolution-factor` R_s,sat
- `--vtk-write-saturated-gas-oil-vaporization-factor` R_v,sat
- `--vtk-write-gas-formation-volume-factor` B_g
- `--vtk-write-oil-formation-volume-factor` B_o
- `--vtk-write-water-formation-volume-factor` B_w
- `--vtk-write-gas-saturation-pressure` p_g,sat
- `--vtk-write-oil-saturation-pressure` p_o,sat
- `--vtk-write-saturation-ratios` actual/max dissolved ratio
- `--vtk-write-intrinsic-permeabilities` intrinsic permeability
- `--vtk-write-potential-gradients` phase pressure potential gradients
- `--vtk-write-filter-velocities` phase filter velocities
- `--vtk-write-diffusion-coefficients` / `--vtk-write-effective-diffusion-coefficients` / `--vtk-write-tortuosities` diffusion
- `--vtk-write-tracer-concentration` tracer concentration
- `--vtk-write-average-molar-masses` average phase mass
- `--vtk-write-extrusion-factor` extrusion factor of the DOFs
- `--vtk-write-dof-index` DOF index
- `--vtk-write-primary-vars` / `--vtk-write-primary-vars-meaning` primary variables
- `--vtk-write-process-rank` MPI process rank

---

## 5. Companion CLI tools

Installed alongside `flow` for pre/post-processing. Useful in a wrapper's
validate / results-extraction stages.

### From `libopm-common-bin`

| Binary | Purpose |
|---|---|
| `summary` | Extract vectors from `.SMSPEC` / `.UNSMRY` summary files. |
| `compareECL` | Compare two Eclipse-format result sets (regression testing). |
| `convertECL` | Convert between formatted and unformatted Eclipse files. |
| `rst_deck` | Build a restart deck from a base deck + restart file. |
| `rewriteEclFile` | Rewrite / normalize Eclipse files. |
| `co2brinepvt` | CO2 / brine PVT property calculator. |
| `opmpack` | Resolve / pack a deck with all INCLUDEs inlined. |
| `opmi` | Deck introspection. |
| `opmhash` | Deck hashing (change detection). |
| `arraylist` | List arrays in an Eclipse file. |
| `hysteresis` | Hysteresis utility. |
| `plot_ms_wells` | Plot multi-segment well data. |

### From `libopm-grid-bin`

| Binary | Purpose |
|---|---|
| `grdecl2vtu` | Convert corner-point grid (GRDECL) to VTU. |
| `mirror_grid` | Mirror a corner-point grid. |

### Python bindings

`python3-opm-common` and `python3-opm-simulators` provide `import opm` for
in-process deck manipulation and simulation control, an alternative to a shell
wrapper.

---

## 6. Wrapper design notes

- Parse `flow --help-all` once per installed version and build the option set
  from it; that output is the source of truth. Do not hardcode assumptions.
- All options are `--name=value`; there are no positional options other than the
  deck path, and no short flags besides `-h`.
- Booleans need explicit `true`/`false`.
- Days-based (`--*-in-days`) and seconds-based (`--*-time-step-size`,
  `--end-time`) time controls both exist. Pick one convention and document it;
  do not mix redundantly.
- `--enable-dry-run=true` gives a fast deck-validation mode (parse + config, no
  simulation).
- For parallel runs, prepend `mpirun -np N`; `--threads-per-process` adds OpenMP
  threads within each rank.
- Capture exit code (nonzero = failure) and surface `CASE.PRT` / `CASE.DBG` from
  `--output-dir` for diagnostics.
- `--parameter-file=params.ini` lets the wrapper pass a generated `.ini` instead
  of a long command line.

### Reference command templates

```bash
# 1. Validate a deck
flow --enable-dry-run=true --output-dir=OUT CASE.DATA

# 2. Standard serial run into a clean output dir
flow --output-dir=OUT CASE.DATA

# 3. Parallel run, 8 ranks, well-aware partitioning
mpirun -np 8 flow --partition-method=zoltanwell --output-dir=OUT CASE.DATA

# 4. Parallel + threads (4 ranks x 2 threads)
mpirun -np 4 flow --threads-per-process=2 --output-dir=OUT CASE.DATA

# 5. GPU-accelerated linear solve
flow --accelerator-mode=cusparse --gpu-device-id=0 --output-dir=OUT CASE.DATA

# 6. Full VTK output for visualization
flow --enable-vtk-output=true \
     --vtk-write-pressures=true --vtk-write-saturations=true \
     --vtk-write-densities=true --output-dir=OUT CASE.DATA

# 7. FORECASTING RESTART (history match -> scenarios). See Section 7.12.
#    Base run, then branch a forecast deck (RESTART keyword -> BASE.UNRST @ step).
flow --output-dir=BASE BASE_CASE.DATA          # step 1: history-match run
cp BASE/BASE_CASE.{UNRST,EGRID,INIT,SMSPEC} .  # step 2: base reachable from deck
flow --output-dir=FCAST FORECAST_SCENARIO.DATA # step 3: forecast from branch step

# 8. Fast serialized restart (resume an interrupted run only; NOT forecasting).
#    Save with 'all' (not 'last'); load an intermediate step; keep OPMRST next to
#    the deck and send --output-dir elsewhere. See Section 7.8.
flow --save-step=all --output-dir=RSTDIR CASE.DATA
flow --load-step=60 --output-dir=OUT2 RSTDIR/CASE.DATA

# 9. Quiet run, no parameter echo (quiet is visible in CASE.PRT, not stdout)
flow --output-mode=log --print-parameters=0 --output-dir=OUT CASE.DATA

# 10. Robust run: relaxed parsing + continue past convergence trouble
flow --parsing-strictness=low \
     --continue-on-convergence-error=true \
     --solver-continue-on-convergence-failure=true \
     --output-dir=OUT CASE.DATA

# 11. Options from an ini file (keys are option names WITHOUT the leading --)
flow --parameter-file=params.ini CASE.DATA

# 12. Post-processing (note the exact arg forms -- see Section 8)
summary -r OUT/CASE FOPR WBHP:PROD            # extract vectors (no extension)
summary -l OUT/CASE                           # list available vectors
compareECL -i -x OUT/CASE REF/CASE 0.05 1e-3  # integration test w/ tolerances
convertECL OUT/CASE.UNRST                     # binary <-> formatted
grdecl2vtu grid.GRDECL                        # corner-point grid to VTU
co2brinepvt density CO2 100 40                # PVT property calculator
```

---

## 7. Tested commands, results, and error resolutions

All commands below were executed on this machine (flow 2026.04, arm64, 3 CPU
cores, no GPU) against `SPE1CASE1.DATA` (the classic 10x10x3 = 300-cell SPE1
black-oil deck from the `opm-tests` repo). Each entry records the exact command,
the observed result, and -- where it failed -- the cause and the fix.

Test deck source: `opm-tests/spe1/SPE1CASE1.DATA` (self-contained, no INCLUDEs,
120 report steps, wells named `PROD` and `INJ`).

### 7.1 Meta / help -- PASS

| Command | Result |
|---|---|
| `flow --version` | `flow 2026.04`, exit 0 |
| `flow --help` | 217 options, exit 0 |
| `flow --help-all` | 283 options, exit 0 |

### 7.2 Deck validation (dry run) -- PASS

```bash
flow --enable-dry-run=true --output-dir=OUT SPE1CASE1.DATA   # exit 0
```
Parses the grid and deck, prints `Simulation turned off`, writes no results.
This is the safe "lint" mode for a wrapper to call before a real run.

### 7.3 Standard serial run -- PASS

```bash
flow --output-dir=OUT SPE1CASE1.DATA         # exit 0, ~0.5 s
```
Produced the full result set in `OUT/`:
`SPE1CASE1.{DBG,EGRID,ESMRY,INIT,PRT,SMSPEC,UNRST,UNSMRY}`.

### 7.4 Parallel MPI run -- PASS (with caveat)

```bash
mpirun --oversubscribe -np 4 flow --partition-method=zoltanwell \
       --output-dir=OUT3 SPE1CASE1.DATA      # exit 0
```
Caveat: this host has only 3 cores, so `mpirun -np 4` fails with a
"not enough slots" error unless `--oversubscribe` is passed. **Prerequisite:**
number of ranks <= physical cores, or add `--oversubscribe`. Results matched the
serial run within tolerance (see 7.11 compareECL).

### 7.5 Hybrid MPI + OpenMP -- PASS

```bash
mpirun --oversubscribe -np 2 flow --threads-per-process=2 \
       --output-dir=OUT4 SPE1CASE1.DATA      # exit 0
```
Total logical workers = ranks x threads. Keep `ranks*threads <= cores` (plus
`--oversubscribe` for the MPI rank count) to avoid contention.

### 7.6 GPU-accelerated linear solve -- FAIL (environment, expected)

```bash
flow --accelerator-mode=cusparse --gpu-device-id=0 --output-dir=OUT5 SPE1CASE1.DATA
# exit 1
# Error: [GpuBridge.cpp:83] cusparseSolver was chosen, but CUDA was not found by CMake
```
Cause: this is an arm64 CPU-only build with no CUDA. Not a command error.
Resolution / wrapper rule: only offer `--accelerator-mode` values other than
`none` when a GPU build + device is present. Detect by probing this command once
and caching the result; treat exit 1 with the `GpuBridge` message as
"GPU unavailable", fall back to `--accelerator-mode=none`.

### 7.7 VTK output -- PASS

```bash
flow --enable-vtk-output=true \
     --vtk-write-pressures=true --vtk-write-saturations=true \
     --vtk-write-densities=true --output-dir=OUT6 SPE1CASE1.DATA   # exit 0
```
Wrote `OUT6/SPE1CASE1-00000.vtu` ... one per report step.
**Prerequisite:** the per-field `--vtk-write-*` switches do nothing unless the
global `--enable-vtk-output=true` is also set.

### 7.8 Serialized fast-restart via .OPMRST -- RESOLVED

IMPORTANT SCOPE: `.OPMRST` is a low-level *exact continuation / crash-recovery*
mechanism, tied to the same flow binary, build and CPU. It bit-for-bit resumes an
interrupted run. It is **NOT** the reservoir-engineering restart workflow used for
forecasting (history match -> branch scenarios). For that, see Section 7.12, which
is the mechanism you almost always want. Use `.OPMRST` only to resume a run that
was stopped, on the same machine.

Four distinct failures were hit and resolved. The working recipe and each pitfall:

**Working recipe:**
```bash
# Step 1 - SAVE: write a persistent .OPMRST (use 'all', not 'last')
flow --save-step=all --output-dir=RSTSRC SPE1CASE1.DATA          # exit 0
#   -> RSTSRC/SPE1CASE1.OPMRST

# Step 2 - place deck NEXT TO the .OPMRST
cp SPE1CASE1.DATA RSTSRC/

# Step 3 - LOAD an INTERMEDIATE step, output to a DIFFERENT dir
flow --load-step=60 --output-dir=RSTOUT RSTSRC/SPE1CASE1.DATA    # exit 0
#   -> "Loading serialized state for report step 60", runs to completion
```

Pitfalls found (all produced hard failures):

1. **`--save-step=last` leaves no file after a clean finish.**
   The log prints nothing persistent and no `.OPMRST` remains. Use
   `--save-step=all` (or a specific step number / `:N`) to get a file that
   survives a successful run. `last`/negative values are aimed at crash recovery
   where only the newest checkpoint is kept and it is removed on normal exit.

2. **The loader looks for `CASE.OPMRST` NEXT TO THE DECK, not in `--output-dir`.**
   `--save-step` writes the `.OPMRST` into `--output-dir`, but `--load-step`
   resolves `CASE.OPMRST` relative to the deck's directory. Symptom:
   `Error locating serialized restart file <deckdir>/CASE.OPMRST`.
   Fix: co-locate the deck and the `.OPMRST` (copy one next to the other).
   Note: `--load-file=<path>` did **not** override this lookup in testing -- the
   error still referenced `<deckdir>/CASE.OPMRST`. Treat co-location as the
   reliable method.

3. **Running the load in the same dir as the `.OPMRST` deletes it at startup.**
   If `--output-dir` equals the directory holding the `.OPMRST`, flow clears the
   file during output initialization before it is read, again giving
   `Error locating serialized restart file`. Fix: send `--output-dir` somewhere
   different from where the `.OPMRST` lives.

4. **`--load-step=0` means "last stored step", which is the end of the run.**
   Loading the final step (120/120 here) leaves nothing to simulate and aborts
   with `SimulatorTimer.cpp:111 Assertion !done() failed` (core dump, exit 134).
   Fix: load a real intermediate report step (e.g. 60). Only use `0`/last when
   the saved run was itself stopped early.

### 7.9 Quiet run -- PASS

```bash
flow --output-mode=log --print-parameters=0 --output-dir=OUT_q SPE1CASE1.DATA  # exit 0
```
Note: `--output-mode=log` still routes messages to the terminal (they go through
the logger). The reduced-noise effect is on the message categories written to
`CASE.PRT`/`CASE.DBG`, not on stdout volume. For a silent wrapper, redirect
stdout/stderr yourself.

### 7.10 Robust run -- PASS

```bash
flow --parsing-strictness=low \
     --continue-on-convergence-error=true \
     --solver-continue-on-convergence-failure=true \
     --output-dir=OUT_r SPE1CASE1.DATA        # exit 0
```
Use for messy decks/first passes. `--parsing-strictness=low` keeps going past
unsupported keywords; the two continue flags avoid bailing on a hard time step.
Results may be less accurate -- do not use for validation runs.

### 7.11 Parameter file (.ini) -- PASS

```bash
cat params.ini
# output-dir=OUT_p
# output-mode=log
# threads-per-process=1
flow --parameter-file=params.ini SPE1CASE1.DATA   # exit 0
```
**Prerequisite:** keys in the `.ini` are the option long-names **without** the
leading `--`, one `key=value` per line. The deck is still passed on the command
line (or via `ecl-deck-file-name=` in the file).

### 7.12 Eclipse-style RESTART forecasting workflow -- RESOLVED (the important one)

This is the reservoir-engineering restart: run a base case (the history-match
period), then branch multiple forecast scenarios from a chosen report step, each
with a different future SCHEDULE. Unlike `.OPMRST` (7.8), this is portable,
Eclipse-compatible, and is what "create restart cases and forecast scenarios"
means in practice.

Mechanism: a restart deck carries a `RESTART` keyword in its SOLUTION section
pointing at the base case's unified restart file and the step to branch from,
plus (usually) `SKIPREST` in SCHEDULE. It reads the saved state (pressures,
saturations, Rs/Rv, well state) from the base `.UNRST` and simulates forward from
there under whatever SCHEDULE the restart deck specifies.

Tested end-to-end with `opm-tests/spe1/SPE1CASE2.DATA` (base, 60-step history) and
`SPE1CASE2_RESTART.DATA` (restart from step 60, the shipped reference case).

**Working recipe:**
```bash
# STEP 1 - run the BASE (history-match) case
flow --output-dir=BASE SPE1CASE2.DATA                 # exit 0
#   -> BASE/SPE1CASE2.UNRST (+ EGRID, INIT, SMSPEC)

# STEP 2 - make the base results reachable from the restart deck.
#   The RESTART keyword resolves its base file relative to the RESTART DECK's
#   directory, NOT --output-dir. Two reliable options:
#   (a) co-locate: put the base UNRST/EGRID/INIT/SMSPEC next to the restart deck
#   (b) QUOTED path in the keyword: RESTART / 'BASE/SPE1CASE2' 60 /
#       An UNQUOTED subdir path FAILS -- see gotcha below.
cp BASE/SPE1CASE2.{UNRST,EGRID,INIT,SMSPEC} .

# STEP 3 - run the restart/forecast deck
flow --output-dir=FCAST SPE1CASE2_RESTART.DATA        # exit 0
#   log: "Initializing report step 60/... 1825 DAYS"  <- started at the branch
```

The restart deck's SOLUTION/SCHEDULE look like:
```
SOLUTION
RESTART
  SPE1CASE2 60 /        -- base case name (no extension), report step to branch at
SCHEDULE
SKIPREST               -- skip re-processing schedule entries before the restart date
... forecast controls / TSTEP ...
```

**Branching scenarios (the actual purpose).** Copy the restart deck, change the
future SCHEDULE, run each into its own output dir. All branches share the same
base `.UNRST` and start from the identical state at the branch step, then diverge.

Verified divergence: base-forecast (producer OPEN) vs a scenario shutting the
producer gave `FOPR = 13894 -> ...` vs `FOPR = 0` respectively, and the summary
files differed (distinct md5). Two scenarios that both leave the wells
constraint-limited produced identical results -- correct physics, just not a
distinguishing change.

**Critical pitfall found -- SKIPREST consumes control keywords placed at the top
of SCHEDULE.** With `SKIPREST`, schedule entries dated at or before the restart
step are fast-forwarded, not applied to the simulated steps. So editing the
`WCONPROD`/`WCONINJE`/`WELOPEN` block that sits at the *start* of SCHEDULE (date
step 0) had ZERO effect -- all edited decks produced byte-identical summaries
(same md5) even when the producer was set to `SHUT`. flow parsed the keyword
(`Reading WELOPEN ...` appears in the PRT) but the well state came from the
restart file. Two ways to actually change the forecast:

1. Place the new controls in a schedule step dated AFTER the restart date (behind
   a later `TSTEP`/`DATES`), so they are applied post-branch. Note this deck uses
   the `START`+`TSTEP` elapsed-time convention; injecting a calendar `DATES`
   keyword failed with `Problem with keyword DATES`. Match the deck's existing
   time convention.
2. Remove `SKIPREST` so the whole SCHEDULE is processed normally, with the
   restart file supplying only the initial state. Dropping `SKIPREST` and adding
   `WELOPEN 'PROD' 'SHUT' /` made FOPR collapse to 0 as expected (md5 changed).
   Trade-off: without `SKIPREST` the pre-branch schedule is re-read (must be
   consistent with the base run); `SKIPREST` is the intended path for pure
   forecasts and is faster, so prefer option 1 for scenario edits.

**Other gotchas:**
- Base results must be co-located with the restart deck, or referenced by a
  **quoted** path in `RESTART`. Missing them gives
  `The restart file SPE1CASE2.UNRST does not exist` / `Problem with keyword RESTART`.
- A subdir path in `RESTART` MUST be quoted. Unquoted `RESTART` newline
  `BASE/SPE1CASE2 60 /` fails at parse time with
  `Internal error: Tried to get uninitialized value from DeckItem index: 0`
  (exit 1) -- the `/` in the path is swallowed as the record terminator, so the
  step number is lost. Quoting the base name works and started at the branch:
  `RESTART` newline `'BASE/SPE1CASE2' 60 /` -> `Initializing report step 60/120`
  (exit 0). For a wrapper, prefer co-location (option a) or always emit the base
  name single-quoted.
- The base case must actually contain the branch step. Report step count in a
  `.UNRST` is listable with `convertECL -l BASE/CASE.UNRST`.
- `--sched-restart=true` (Section 3.15) makes flow initialize wells/groups from
  the historical SCHEDULE at restart instead of purely from the restart-file
  well state. Tested with this workflow: exit 0, still `Initializing report step
  60`. Default (`false`) takes well state from the `.UNRST`; set true when the
  base run's well configuration must be rebuilt from the deck's SCHEDULE.
- `rst_deck` (Section 8.4) automates building a restart deck from a base deck +
  `.UNRST` (inserts `RESTART`, optionally `SKIPREST`), so a wrapper can generate
  scenario skeletons programmatically instead of hand-editing.

**Choosing between the two restart mechanisms:**

| Need | Use |
|---|---|
| Resume an interrupted run, same machine/build, exact | `.OPMRST` (7.8) |
| Forecast / branch scenarios from a history match | `RESTART` keyword (7.12) |
| Portable, Eclipse-compatible, shareable restart | `RESTART` keyword (7.12) |

---

## 8. Tested companion tools

All run against the `OUT/` results from 7.3 unless noted.

### 8.1 `summary` -- extract summary vectors -- PASS

```bash
summary -l OUT/SPE1CASE1               # list all available vectors
summary -r OUT/SPE1CASE1 FOPR WBHP:PROD FGOR   # extract, report steps only
```
Gotchas learned:
- Argument is the case basename **without extension** (`OUT/SPE1CASE1`, not
  `.SMSPEC`). The template in some docs showing `CASE.SMSPEC` is misleading.
- Options (`-l`, `-r`, `-n`, `-o file`) must come **before** the arguments.
  There is no `--long` form; `summary --help` errors with `invalid option`.
- Vector names must exist in the deck. `WBHP:PRODUCER` failed with
  `Key ... not found`; the actual well is `PROD` (`WBHP:PROD`). Use `-l` first to
  discover valid names.
- Piping into `head` yields exit code 141 (SIGPIPE) -- harmless, not a tool
  error. A wrapper should treat 141-on-pipe as success.

### 8.2 `compareECL` -- compare two result sets -- PASS

```bash
compareECL -i -x OUT/SPE1CASE1 OUT3/SPE1CASE1 0.05 1e-3   # integration test
compareECL -t SMRY -k WBHP:PROD OUT/SPE1CASE1 OUT3/SPE1CASE1 1.0 1e-2
```
Requires **four positional args**: ref case, test case, absolute tol, relative
tol (0-1). Options precede them.
Learned:
- A bare `compareECL A B` (no tolerances) errors -- the tolerances are required.
- Comparing serial vs parallel with the default full regression test throws
  `Keywords not identical in Init file` because parallel runs emit a different
  INIT keyword set (e.g. TRAN*). Use `-x` (allow extra keywords in case 2) or
  `-i` (integration test: compares SGAS/SWAT/PRESSURE + WOPR/WGPR/WWPR/WBHP only)
  to get a physically meaningful comparison. With `-i -x` and a 5%/1e-3 tolerance
  the serial and 4-rank parallel SPE1 results matched (exit 0).
- `-k KEYWORD` restricts to one keyword; `-t {UNRST,EGRID,INIT,RFT,SMRY,RSM}`
  restricts to one file type.

### 8.3 `convertECL` -- format conversion -- PASS

```bash
convertECL OUT/SPE1CASE1.UNRST     # binary -> formatted (.FUNRST)
convertECL -l OUT/SPE1CASE1.UNRST  # list report step numbers
convertECL -g -o grid.grdecl OUT/SPE1CASE1.EGRID   # -> grdecl
```
Direction is automatic: binary input yields formatted output and vice-versa.
Takes exactly one input file (plus options before it).

### 8.4 `rst_deck` -- build a restart deck -- PASS

```bash
rst_deck -s -m inline SPE1CASE1.DATA OUT/SPE1CASE1:60 SPE1_RESTART
rst_deck SPE1CASE1.DATA OUT/SPE1CASE1:60           # dry -> restart deck on stdout
```
Learned:
- `-m` takes `share` (default) | `inline` | `copy`, **not** `none`. Passing an
  invalid mode exits 1.
- Restart source form is `basename:N` (`OUT/SPE1CASE1:60` = report step 60) or a
  path to an existing restart file.
- Output basename arg is written **verbatim** (produced a file literally named
  `SPE1_RESTART`, no `.DATA` appended). Add the extension yourself if wanted.
- Correctly rewrote the SOLUTION section with a `RESTART` keyword
  (`'OUT/SPE1CASE1' 60 /`) and, with `-s`, inserted `SKIPREST` in SCHEDULE.
- The informational text about retained SOLUTION keywords prints to **stderr**;
  do not treat stderr output alone as failure -- check the exit code.

### 8.5 `opmpack` -- inline all INCLUDEs -- PASS

```bash
opmpack SPE1CASE1.DATA > packed.DATA        # exit 0
```
Flattens a deck (resolves INCLUDE/paths) into a single self-contained file.
Useful for a wrapper to snapshot exactly what was run.

### 8.6 `opmi` / `opmhash` -- introspection -- PASS

```bash
opmi SPE1CASE1.DATA        # lists every keyword as it is parsed, with line refs
opmhash SPE1CASE1.DATA     # per-keyword content hash (diff two decks for changes)
```

### 8.7 `co2brinepvt` -- PVT calculator -- PASS

```bash
co2brinepvt density   CO2   100 40        # -> 628.29  (kg/m3 at 100 bar, 40 C)
co2brinepvt viscosity CO2   100 40        # -> 4.779e-05
co2brinepvt density   brine 100 40 1.0    # -> 1033.81 (salinity 1.0 mol/kg)
```
Signature: `co2brinepvt <prop> <phase> <p[bar]> <T[C]> [salinity] [rs] [rv] ...`.
`prop in {density,invB,B,viscosity,rsSat,internalEnergy,enthalpy,diffusionCoefficient}`,
`phase in {CO2,brine}`. Runs standalone -- no deck needed.

### 8.8 `grdecl2vtu` -- corner-point grid to VTU -- PASS

```bash
grdecl2vtu SPE9.GRDECL      # -> SPE9.vtu, exit 0
```
**Prerequisite:** input must be a corner-point grid in GRDECL format
(COORD/ZCORN). SPE1 uses a cartesian DX/DY/DZ/TOPS grid and has no `.GRDECL`, so
a corner-point deck (e.g. `opm-tests/spe9/SPE9.GRDECL`) was used. To visualize a
cartesian case, first export a grid with `convertECL -g` from the `.EGRID`.

---

## 9. Prerequisites and safety checklist for a wrapper

Consolidated rules for driving `flow` safely and reproducibly.

**Before a run:**
- Verify the deck path exists and ends in `.DATA`. Resolve INCLUDEs are present
  (or `opmpack` first).
- Optionally lint with `flow --enable-dry-run=true` and fail fast on nonzero exit.
- Create the `--output-dir` (flow writes into it; it is not always auto-created
  cleanly across versions -- `mkdir -p` it yourself).

**Parallelism:**
- `mpirun -np N`: require `N <= nproc`, else add `--oversubscribe`. Detect cores
  with `nproc`.
- Keep `ranks * threads_per_process <= cores`.
- Parallel runs change the INIT keyword set; compare against references with
  `compareECL -i -x` or `-k`, not the default full regression.

**GPU:**
- `--accelerator-mode` other than `none` requires a CUDA/HIP build + device.
  Probe once; on the `GpuBridge`/`CUDA was not found` error fall back to `none`.

**Forecasting restart (RESTART keyword -> .UNRST) -- the default engineering path:**
- Run the base (history-match) case first; keep its `.UNRST`/`.EGRID`/`.INIT`/
  `.SMSPEC`.
- The `RESTART` keyword resolves the base file relative to the RESTART DECK's
  directory (not `--output-dir`): co-locate base results with the forecast deck,
  or put a path in the keyword. Missing -> `restart file ... does not exist`.
- Branch scenarios by copying the forecast deck and changing the future SCHEDULE.
- With `SKIPREST`, control edits at the TOP of SCHEDULE (pre-branch date) are
  IGNORED -- the state comes from the restart file. Put scenario changes AFTER the
  restart date, or drop `SKIPREST` to process the full schedule. Verify a scenario
  actually diverges (diff the `.UNSMRY` md5 / `summary` vectors); identical md5
  means the edit did not take.
- Match the deck's time convention (this SPE1 deck uses `START`+`TSTEP`; injecting
  `DATES` errored). `rst_deck` can generate the restart deck skeleton.

**Fast serialized restart (.OPMRST) -- resume interrupted runs only, not forecasts:**
- Save with `--save-step=all` (or `:N`), not `last`, to get a persistent file.
- Co-locate the deck and `CASE.OPMRST`; send `--output-dir` elsewhere.
- Load a real intermediate step; never `--load-step=0` unless the source run was
  stopped early (0/last = end of run = assertion abort).
- Binary/build/CPU specific -- do not use for portable or scenario restarts.

**Exit codes / output parsing:**
- `0` = success. `1` = handled error (deck/config/solver); read the last
  non-stack-trace lines for the `Error:`/`Simulation aborted` message.
- `134` (SIGABRT / core dump) = an internal assertion (e.g. restart-at-end). Bug
  or misuse, not a converged result.
- Pipe consumers may report `141` (SIGPIPE) -- not a flow failure.
- Real diagnostics live in `CASE.PRT` (human) and `CASE.DBG` (verbose) inside
  `--output-dir`. Surface these on failure.

**Option handling:**
- All flow options are `--name=value`; booleans need explicit `true`/`false`;
  only `-h` is short.
- Companion tools (`summary`, `compareECL`, `convertECL`, `rst_deck`) use
  **single-dash** short options that must come **before** positional args, and
  take case basenames **without** extension. Do not assume `--long` forms.
- Build the flow option list by parsing `flow --help-all` once per version; treat
  it as the source of truth and reject unknown options before launching (flow
  aborts on an unrecognized option).

**Determinism:**
- Snapshot the exact command line and, ideally, `opmpack` output and `opmhash`
  of the deck alongside results so a run can be reproduced/diffed later.
