---
name: replay-a-proof
description: Use when someone wants to contribute compute by re-running Comparator on one statement of OpenAI's mathematics release on their own Linux machine, and to record a replay receipt (contributions/replays/<statement-id>/<github-handle>-<YYYYMMDD>.json). Gives the setup (elan, Comparator, lean4export, landrun), the upstream commands, the sandboxed run, how to read the outcome, and how to fill each receipt field.
---

# Replay a proof

A replay re-runs the Comparator check for one statement on your own machine and records what happened. Independent replays show that the check can be reproduced away from the machines that produced it. A replay checks the proof against the challenge statement. Whether that statement says what the paper says is a separate question, answered by a statement check (`skills/check-a-statement/SKILL.md`).

The upstream instructions are `lean/README.md` and `lean/ComparatorChallenges/README.md` in openai/math. [Comparator's own README](https://github.com/leanprover/comparator) explains what it guarantees and under which assumptions. This skill follows both.

## What you need

- **Linux.** Comparator runs each build inside landrun, a sandbox built on the Linux kernel's Landlock feature, so it needs a recent Linux kernel with Landlock enabled (landrun's README gives the minimum version). macOS and Windows cannot run it directly; a Linux virtual machine or a rented cloud machine can.
- **systemd with a user session**, for the sandboxed command recommended below. Check with `systemctl --user show-environment`.
- **git, curl and Go.** Go builds landrun.
- **Time, memory and disk.** Comparator builds the statement's proof and everything it imports. Mathlib arrives prebuilt, but OpenAI's modules and the third-party Lean libraries they use are compiled on your machine. Some statements build in minutes on a large machine and others take hours, and you should expect to need tens of gigabytes of free disk. Your receipt records the time and the machine, which tells the next person what to expect.
- **An ordinary user account.** Do not run any of this as root.

Do not build the whole library: the upstream README warns that it is a single large library and recommends compiling small portions at a time. Comparator builds only what the chosen statement needs.

The upstream README also warns that compiling the entire library may fail on Linux when `vm.max_map_count` is too low. One statement builds far less, but if a build fails with a memory-mapping error, upstream suggests building Lean with the CMake option `-DMMAP=OFF`, and possibly setting `GLIBC_TUNABLES=glibc.malloc.mmap_max=0:glibc.malloc.arena_max=1` when running Lean or Lake. Raising the limit with `sysctl` is the other common remedy, and needs administrator rights; `sysctl vm.max_map_count` shows the current value.

## 1. Install Lean's version manager

```sh
curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh
export PATH="$HOME/.elan/bin:$PATH"
```

elan installs whichever Lean version a project asks for. The release asks for the version in `lean/lean-toolchain`.

## 2. Build Comparator and its two helpers

```sh
mkdir -p ~/comparator-tools && cd ~/comparator-tools

git clone https://github.com/leanprover/comparator.git
(cd comparator && lake build comparator)

git clone https://github.com/leanprover/lean4export.git
(cd lean4export && lake build lean4export)

git clone https://github.com/zouuup/landrun.git
(cd landrun && go build -o landrun cmd/landrun/main.go)

export PATH="$HOME/comparator-tools/comparator/.lake/build/bin:$HOME/comparator-tools/lean4export/.lake/build/bin:$HOME/comparator-tools/landrun:$PATH"
```

Comparator's README asks for landrun built from its main branch, and for a lean4export version compatible with the Lean version of the project you check. If Comparator later fails while exporting, compare lean4export's own `lean-toolchain` file with the release's `lean/lean-toolchain`, check out a lean4export commit that matches, and rebuild.

Record the three commits for your receipt:

```sh
git -C ~/comparator-tools/comparator rev-parse HEAD
git -C ~/comparator-tools/lean4export rev-parse HEAD
git -C ~/comparator-tools/landrun rev-parse HEAD
```

## 3. Get the release at the pinned commit

```sh
cd ~
git clone https://github.com/openai/math.git openai-math
cd openai-math
git checkout fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb
cd lean
```

The commit is the one in the atlas's `upstream.json`; use the newer one if it has changed. Use a fresh clone, and do not build anything in it before you run Comparator. Comparator's guarantee assumes the proof has not been compiled outside its sandbox first.

## 4. Fetch the dependencies

```sh
lake update
lake exe cache get
git status --short
```

`lake update` fetches the pinned dependencies and applies the release's compatibility patches (`lean/patches/README.md` explains them). `lake exe cache get` downloads prebuilt Mathlib. If `git status` shows that `lake-manifest.json` changed, record that in the receipt's `notes`.

## 5. Read the statement's configuration

```sh
cat ComparatorChallenges/<Name>.json
```

Note `permitted_axioms`, which goes into your receipt, and `solution_module`, the part of OpenAI's library that will be built.

## 6. Run Comparator in the sandbox

The upstream README runs `lake env comparator ComparatorChallenges/<Name>.json` from `lean/`. Comparator's README recommends wrapping it in `systemd-run`, with Unix-domain sockets blocked, to guard against a known weakness in landrun. Run this from `lean/`, inside `tmux` or `screen` so a dropped connection does not stop a long build:

```sh
start=$(date +%s)
systemd-run --user --pipe --property=RestrictAddressFamilies=~AF_UNIX \
  -E PATH="$PATH" --working-directory="$PWD" -- \
  lake env comparator ComparatorChallenges/<Name>.json > comparator.log 2>&1
status=$?
end=$(date +%s)
echo "exit status $status after $((end - start)) seconds"
tail -n 5 comparator.log
```

If your system has no systemd user session, run the upstream command without the wrapper, `lake env comparator ComparatorChallenges/<Name>.json > comparator.log 2>&1`, and say so in `notes`: the sandbox is then weaker.

## 7. Read the outcome

| What you see | `result` |
|---|---|
| Exit status 0, and the log ends with `Your solution is okay!` | `accepted` |
| Comparator reports a statement mismatch (a message containing "do not match" or "does not match"), an illegal axiom (`Illegal axiom detected`), or a kernel rejection ("rejects the solution") | `rejected` |
| The run stopped before a verdict: a build failure, a missing tool, running out of memory or disk, an interruption | `error` |

Every outcome is worth recording. A rejection at the pinned commit is also worth a problem report with the end of the log (`skills/report-a-problem/SKILL.md`).

## 8. Fill in the receipt

In your clone of the atlas:

```sh
mkdir -p contributions/replays/<Name>
cp contributions/_templates/replay.json contributions/replays/<Name>/<your-github-handle>-$(date +%Y%m%d).json
```

| Field | Where it comes from |
|---|---|
| `statement` | the challenge name, `<Name>` |
| `upstream_commit` | `git rev-parse HEAD` in your openai-math clone |
| `lean_toolchain` | the contents of `lean/lean-toolchain`, such as `leanprover/lean4:v4.34.1` |
| `comparator_commit` | the Comparator commit you recorded in step 2 |
| `lean4export_commit`, `landrun_commit` | optional; the other two commits from step 2 |
| `result` | `accepted`, `rejected` or `error`, from step 7 |
| `axioms` | the `permitted_axioms` list from the challenge's `.json`: the axiom budget Comparator enforced |
| `wall_time_seconds` | the seconds printed in step 6, as a number without quotes |
| `machine.os` | for example `. /etc/os-release; echo "$PRETTY_NAME, Linux $(uname -r)"` |
| `machine.cpu` | the "Model name" line of `lscpu`, and the core count from `nproc` |
| `machine.ram_gb` | the total in the "Mem" row of `free -g`, as a number |
| `contributor` | your name and GitHub handle |
| `log_sha256` | the first field printed by `sha256sum comparator.log` |
| `notes` | optional; anything unusual, such as a changed `lake-manifest.json`, a run without the systemd wrapper, or a retry |
| `date` | `date +%F`; it must match the date in the file name |

Delete the optional lines you do not use. If the log is under 2 MB, put it beside the receipt with the same name ending in `.log`, or compress it with `gzip` to end in `.log.gz`; the checker then confirms that `log_sha256` matches it. A larger log goes in the pull request as an attachment.

## 9. Check and submit

```sh
python3 scripts/check_contributions.py contributions/replays/<Name>/<your-github-handle>-<YYYYMMDD>.json
```

Open a pull request with the receipt (and the log, if small). Without git, paste the receipt into the "Share a replay" issue form.

## What a replay shows

An `accepted` receipt shows that on your machine, with the recorded tool versions, Comparator accepted OpenAI's proof of this statement within the recorded axiom budget. Comparator's README lists the assumptions this rests on: the challenge file, its imports (here Mathlib) and the project's lakefile are trusted; the proof was not compiled before Comparator ran; landrun's sandbox holds; the Lean kernel is correct; and the run was not made by a privileged user. A replay does not show that the statement matches the paper.
