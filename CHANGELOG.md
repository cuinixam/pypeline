# CHANGELOG


## v1.26.0 (2026-02-01)

### Features

- Make WestInstall step generic for custom execution contexts
  ([`dfa5ffe`](https://github.com/cuinixam/pypeline/commit/dfa5ffea89bd40b6e6ffa08462ccc0be4f539c83))


## v1.25.0 (2026-01-31)

### Features

- Make west install step workspace configurable
  ([`9c1662e`](https://github.com/cuinixam/pypeline/commit/9c1662e04b182f48800ddab1d2f2adc9f2b665f3))

- Support multiple west manifests and track installed modules
  ([`493bfa8`](https://github.com/cuinixam/pypeline/commit/493bfa81db93d1d211560d8a1c0032605287ab6b))


## v1.24.1 (2026-01-18)

### Bug Fixes

- Bootstrap config merge type conflict
  ([`0f2c963`](https://github.com/cuinixam/pypeline/commit/0f2c963e7f7727e320d86cf5f6f8e5e895ceb2a4))


## v1.24.0 (2026-01-17)

### Features

- Create user bootstrap script if not existing
  ([`4cce791`](https://github.com/cuinixam/pypeline/commit/4cce791f95d77fb1d44f7c5d6f8f8806bfcb1d36))


## v1.23.2 (2026-01-17)

### Bug Fixes

- Venv not self updating if dependecies change
  ([`957f52c`](https://github.com/cuinixam/pypeline/commit/957f52c757d717428cfed217592b83fbb3d6dcc8))


## v1.23.1 (2026-01-15)

### Bug Fixes

- Uv package manager ignores python version
  ([`c0a0076`](https://github.com/cuinixam/pypeline/commit/c0a007645c60359c01c0178f9d0fc2a85aca7832))


## v1.23.0 (2026-01-15)

### Features

- Fallback to generic `python` with version verification
  ([`00cd443`](https://github.com/cuinixam/pypeline/commit/00cd4435d6c032293e49372a582d8556f31b2763))

Fixes #7

- Generate platform specific env setup scripts
  ([`afe8b24`](https://github.com/cuinixam/pypeline/commit/afe8b240e8815c059fa9cdf5da89ded19a58347f))


## v1.22.0 (2026-01-14)

### Features

- Add option to override the python version from command line
  ([`3868760`](https://github.com/cuinixam/pypeline/commit/386876093c1ec3af91739e72579a544e3709df66))


## v1.21.1 (2026-01-13)

### Bug Fixes

- Bootstrap.json is created in the wrong directory
  ([`e295853`](https://github.com/cuinixam/pypeline/commit/e295853004cf40e25dba561dc13c0f5ea5ee77e2))


## v1.21.0 (2026-01-13)

### Features

- Create env step finds python executable based on python version config
  ([`4c49076`](https://github.com/cuinixam/pypeline/commit/4c4907681ac069bcb3c3b605c072823cdd4cf37d))

- Scoop install does nothing for non windows platforms
  ([`f3bddb5`](https://github.com/cuinixam/pypeline/commit/f3bddb5e80bbaf0ed2df0b4ee52eb20c0329840e))

- Update bootstrap to isolate package manager
  ([`29a9cfe`](https://github.com/cuinixam/pypeline/commit/29a9cfe2aaf54a3c14aa1ace5f08cb6af3d58cce))


## v1.20.0 (2026-01-05)

### Features

- Read venv installed dirs if available
  ([`b6e7ca0`](https://github.com/cuinixam/pypeline/commit/b6e7ca08f6cb56e854b90d385a47452947fedb52))


## v1.19.1 (2025-08-22)

### Bug Fixes

- .env variables are not available for subsequent steps
  ([`2b8d768`](https://github.com/cuinixam/pypeline/commit/2b8d768a0c5f74a4a70a0e830236e375452f6ca8))


## v1.19.0 (2025-08-15)

### Features

- Only load the steps scheduled to be executed
  ([`b84adbc`](https://github.com/cuinixam/pypeline/commit/b84adbcd7726899a9bff6941ed391d4cef1feb55))


## v1.18.2 (2025-06-28)

### Bug Fixes

- Add missing dependency for the west step
  ([`5c49bd4`](https://github.com/cuinixam/pypeline/commit/5c49bd4596ebd1984a86a2c5b26a9034a1bd9190))


## v1.18.1 (2025-06-26)

### Bug Fixes

- Pin pip-system-certs to avoid breaking changes
  ([`35004c4`](https://github.com/cuinixam/pypeline/commit/35004c4e2b6b2c48e0fdb4418a0cc01248494116))


## v1.18.0 (2025-06-04)

### Features

- Support option to skip venv pristine creation
  ([`527fb49`](https://github.com/cuinixam/pypeline/commit/527fb4973de923a068855bb4a48beebeb41a9832))


## v1.17.0 (2025-06-04)

### Features

- Deploy the bootstrap file in the project
  ([`52f8b73`](https://github.com/cuinixam/pypeline/commit/52f8b73a5bc3eef900a8cd2cc1c7d29eb683ae62))


## v1.16.1 (2025-05-03)

### Bug Fixes

- Create env retriggered because of different bootstrap location
  ([`ed2e627`](https://github.com/cuinixam/pypeline/commit/ed2e627a4f0eb785daa776f1d8019bc1b17af986))


## v1.16.0 (2025-04-23)

### Features

- Internal bootstrap runs if config changes
  ([`f95d0c8`](https://github.com/cuinixam/pypeline/commit/f95d0c83faba67dc08484ef27c73948b66203712))


## v1.15.1 (2025-04-17)

### Bug Fixes

- Boolean inputs require a value
  ([`7127064`](https://github.com/cuinixam/pypeline/commit/71270645cabb3ad3551d71ca08c1bf135be45061))


## v1.15.0 (2025-04-17)

### Features

- Integrate internal bootstrap to create env
  ([`006000b`](https://github.com/cuinixam/pypeline/commit/006000b67c6d782d5918965144f4513a78576db8))


## v1.14.0 (2025-04-14)

### Features

- Run steps if the pypeline was updated
  ([`30d46ca`](https://github.com/cuinixam/pypeline/commit/30d46ca2e4be4c203fe5d01e15a027773a6f9a2e))


## v1.13.0 (2025-04-14)

### Features

- Add environment variables to the execution context
  ([`81db839`](https://github.com/cuinixam/pypeline/commit/81db839be4e45b3be61f94953ed4612828b8b713))

- Scoop install register the apps env vars
  ([`5055956`](https://github.com/cuinixam/pypeline/commit/50559569790c372e9a07f441299a0fb5dd4e729b))


## v1.12.0 (2025-04-04)

### Features

- Support pypeline inputs configuration
  ([`8aa4587`](https://github.com/cuinixam/pypeline/commit/8aa4587d4c700d51a77aed4f04fbd6b47fe6a1b0))


## v1.11.0 (2025-04-04)

### Features

- Support scoop apps versions
  ([`2ea7141`](https://github.com/cuinixam/pypeline/commit/2ea7141d3bee48f0ea0ef0aeb97df181a81eee4a))


## v1.10.0 (2025-04-03)

### Features

- Add step to generate env setup scripts
  ([`037a74d`](https://github.com/cuinixam/pypeline/commit/037a74da00347684debdb86ef234e72aae9fcccd))


## v1.9.1 (2025-03-24)

### Bug Fixes

- Can not select multiple steps
  ([`8bdccaf`](https://github.com/cuinixam/pypeline/commit/8bdccaf940c1cabe9e564b486f619ce4581e76ef))


## v1.9.0 (2025-03-24)

### Features

- Support multiple steps selection
  ([`d655cd1`](https://github.com/cuinixam/pypeline/commit/d655cd1c6b821bfc7aa1cb8ae9b1c65433b2b903))


## v1.8.1 (2025-02-16)

### Bug Fixes

- Can not run external processes on WSL
  ([`d622cae`](https://github.com/cuinixam/pypeline/commit/d622cae99e0f621cdd658046a646f166b17b88f7))


## v1.8.0 (2025-02-16)

### Features

- Add bootstrap support for non-windows machines
  ([`db57e12`](https://github.com/cuinixam/pypeline/commit/db57e12d66da5686475f7d951acabcb929c7a121))


## v1.7.0 (2025-02-16)

### Features

- Add support for custom config file
  ([`1344a9b`](https://github.com/cuinixam/pypeline/commit/1344a9bf07488f519581dfc6518dfcdae226f12c))


## v1.6.0 (2025-01-21)

### Features

- Data register supports dynamically loaded classes
  ([`badb2aa`](https://github.com/cuinixam/pypeline/commit/badb2aa2a94799e2e48887b773ea68a840ca1748))


## v1.5.0 (2025-01-20)

### Features

- Add data registry to execution context
  ([`4e011ca`](https://github.com/cuinixam/pypeline/commit/4e011caea4f70ad53de7e3a23ce00b912d48146c))


## v1.4.0 (2025-01-15)

### Features

- Support run commands with arguments
  ([`44d3b76`](https://github.com/cuinixam/pypeline/commit/44d3b768f14ac6f6fa3861262a68a1bc68bee79d))


## v1.3.0 (2024-12-17)

### Features

- Groups are optional
  ([`3aadae1`](https://github.com/cuinixam/pypeline/commit/3aadae19fff50cce57c04546e01b14ff94608645))


## v1.2.0 (2024-11-28)

### Features

- Scoop install works behind a proxy
  ([`ad88d50`](https://github.com/cuinixam/pypeline/commit/ad88d505bbcff620927d65b2a77bdae3c70af37f))


## v1.1.0 (2024-11-23)

### Features

- Use avengineers/bootstrap
  ([`05b257b`](https://github.com/cuinixam/pypeline/commit/05b257b0ac9821b42a04286694976fa8698b3157))


## v1.0.0 (2024-09-29)

### Features

- Support custom execution context
  ([`0514d64`](https://github.com/cuinixam/pypeline/commit/0514d64e8f255758dc18152e6177f9f902450354))


## v0.3.1 (2024-06-20)

### Bug Fixes

- Steps with command are not found
  ([`1af9fc3`](https://github.com/cuinixam/pypeline/commit/1af9fc3a36b6b19abea793d9d7d68e64d357bbbf))


## v0.3.0 (2024-05-15)

### Documentation

- Pypeline.yaml configuration
  ([`40d7b15`](https://github.com/cuinixam/pypeline/commit/40d7b1551adc8a6e0429669f72076ad25f4eb881))

### Features

- Add support for running commands
  ([`7f56565`](https://github.com/cuinixam/pypeline/commit/7f56565dcfa21e4d5f660cef5ac8a00fe02d8f9a))


## v0.2.2 (2024-04-15)

### Bug Fixes

- Pypeline.exe script not working
  ([`7797683`](https://github.com/cuinixam/pypeline/commit/77976836e2afd94793cbe9bc93a4950319242795))


## v0.2.1 (2024-04-14)

### Bug Fixes

- Invalid configuration exceptions not caught
  ([`0576a4b`](https://github.com/cuinixam/pypeline/commit/0576a4b976b588c5804c78df9cdf48bd0a9e066f))


## v0.2.0 (2024-04-14)

### Bug Fixes

- Scoop install not executed if scoop dirs file is deleted
  ([`c2fb9e3`](https://github.com/cuinixam/pypeline/commit/c2fb9e3ea05527a0a6802df61555a2e27a160656))

### Documentation

- Add how to kickstart a project with pypeline
  ([`cefe759`](https://github.com/cuinixam/pypeline/commit/cefe7591fb3393fe2e05ecafbf9105d873f90a90))

### Features

- Add dry run option
  ([`e20cfa5`](https://github.com/cuinixam/pypeline/commit/e20cfa5e690c567d94103e838f49fb5a4f64bc5e))

- Create venv bootstrap script path is configurable
  ([`cb1109b`](https://github.com/cuinixam/pypeline/commit/cb1109b79c81e5a9e2ef9e12050c1e38e4fc746f))


## v0.1.1 (2024-04-12)

### Bug Fixes

- Pyyaml explicit dependency missing
  ([`5876cc3`](https://github.com/cuinixam/pypeline/commit/5876cc3af1e19f776dfc7460e20861149cf3ab7a))


## v0.1.0 (2024-04-12)

### Features

- Add project kick-starter
  ([`8ab9cfa`](https://github.com/cuinixam/pypeline/commit/8ab9cfa5d2c613c24e50fcdf55949ac9e5fc8b90))

- Support scoop and west
  ([`0a0f26b`](https://github.com/cuinixam/pypeline/commit/0a0f26b53a35e98f41970ddc4e5f2ae491967570))
