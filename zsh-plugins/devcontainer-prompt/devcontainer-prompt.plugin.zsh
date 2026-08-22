# Show an indicator when the current directory belongs to a Dev Container.
# Non-running containers use a warning color.
#
# Configuration variables should be set before Oh My Zsh is sourced:

: ${DEVCONTAINER_PROMPT_TEXT:="⬢"}
: ${DEVCONTAINER_PROMPT_COLOR:=cyan}
: ${DEVCONTAINER_PROMPT_WARNING_COLOR:=214}
: ${DEVCONTAINER_PROMPT_CACHE_TTL:=3}
: ${DEVCONTAINER_PROMPT_DOCKER:=docker}
: ${DEVCONTAINER_PROMPT_SHOW_NAME:=true}
: ${DEVCONTAINER_PROMPT_MATCH_SUBDIRECTORIES:=true}

typeset -g DEVCONTAINER_PROMPT=''
typeset -g DEVCONTAINER_PROMPT_CONTAINER=''

typeset -g  _DEVCONTAINER_PROMPT_LAST_PWD=''
typeset -gi _DEVCONTAINER_PROMPT_LAST_CHECK=0

autoload -Uz add-zsh-hook
zmodload zsh/datetime 2>/dev/null || true


_devcontainer_prompt_now() {
  emulate -L zsh

  if (( ${+EPOCHSECONDS} )); then
    REPLY=$EPOCHSECONDS
  else
    REPLY=$(command date +%s)
  fi
}


_devcontainer_prompt_invalidate() {
  typeset -g  _DEVCONTAINER_PROMPT_LAST_PWD=''
  typeset -gi _DEVCONTAINER_PROMPT_LAST_CHECK=0
}


_devcontainer_prompt_precmd() {
  emulate -L zsh
  setopt local_options no_sh_word_split

  _devcontainer_prompt_now

  local -i now=$REPLY
  local -i ttl=${DEVCONTAINER_PROMPT_CACHE_TTL:-3}

  (( ttl < 0 )) && ttl=0

  if [[ $_DEVCONTAINER_PROMPT_LAST_PWD == $PWD ]] &&
     (( now - _DEVCONTAINER_PROMPT_LAST_CHECK < ttl )); then
    return 0
  fi

  typeset -g  _DEVCONTAINER_PROMPT_LAST_PWD=$PWD
  typeset -gi _DEVCONTAINER_PROMPT_LAST_CHECK=$now

  # Clear stale state before contacting Docker.
  typeset -g DEVCONTAINER_PROMPT=''
  typeset -g DEVCONTAINER_PROMPT_CONTAINER=''

  local docker_cmd=${DEVCONTAINER_PROMPT_DOCKER:-docker}

  whence -p "$docker_cmd" >/dev/null 2>&1 || return 0

  local output
  output=$(
    "$docker_cmd" ps --all \
      --filter 'label=devcontainer.local_folder' \
      --format '{{.Names}}{{"\t"}}{{.Label "devcontainer.local_folder"}}{{"\t"}}{{.State}}' \
      2>/dev/null
  ) || return 0

  [[ -n $output ]] || return 0

  local cwd=${PWD:A}
  local row name root state remainder
  local best_name=''
  local best_root=''
  local best_state=''
  local -i best_root_length=0
  local -i matched=0
  local -a rows

  rows=("${(@f)output}")

  for row in "${rows[@]}"; do
    [[ $row == *$'\t'*$'\t'* ]] || continue

    name=${row%%$'\t'*}
    remainder=${row#*$'\t'}
    root=${remainder%%$'\t'*}
    state=${remainder#*$'\t'}

    [[ -n $root ]] || continue

    # Canonicalize paths so symlinks and redundant components do not
    # cause false mismatches.
    root=${root:A}
    matched=0

    if [[ $cwd == $root ]]; then
      matched=1
    elif [[ ${DEVCONTAINER_PROMPT_MATCH_SUBDIRECTORIES:-true} == true &&
            $cwd == "$root"/* ]]; then
      matched=1
    fi

    (( matched )) || continue

    # Prefer the most specific workspace when workspaces are nested. If
    # multiple containers belong to the same workspace, prefer a running one.
    if (( ${#root} > best_root_length )) ||
       { (( ${#root} == best_root_length )) &&
         [[ $state == running && $best_state != running ]]; }; then
      best_name=$name
      best_root=$root
      best_state=$state
      best_root_length=${#root}
    fi
  done

  [[ -n $best_root ]] || return 0

  local text=${DEVCONTAINER_PROMPT_TEXT:-"⬢ devcontainer"}

  if [[ ${DEVCONTAINER_PROMPT_SHOW_NAME:-false} == true ]]; then
    text+=":${best_name}"
  fi

  local color=${DEVCONTAINER_PROMPT_COLOR:-cyan}

  if [[ $best_state != running ]]; then
    color=${DEVCONTAINER_PROMPT_WARNING_COLOR:-214}
  fi

  typeset -g DEVCONTAINER_PROMPT_CONTAINER=$best_name
  typeset -g DEVCONTAINER_PROMPT="%F{${color}}${text}%f "
}


# Force a new Docker query on the next prompt.
devcontainer_prompt_refresh() {
  _devcontainer_prompt_invalidate
  _devcontainer_prompt_precmd
}


add-zsh-hook chpwd  _devcontainer_prompt_invalidate
add-zsh-hook precmd _devcontainer_prompt_precmd
