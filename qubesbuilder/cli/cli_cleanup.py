import os
import shutil
from datetime import datetime, timedelta

import click

from qubesbuilder.cli.cli_base import aliased_group, ContextObj
from qubesbuilder.common import get_archive_name
from qubesbuilder.component import QubesComponent, ComponentError


@aliased_group("cleanup", chain=True)
@click.option(
    "--dry-run",
    default=False,
    is_flag=True,
    help="Dry run. It won't delete anything.",
)
@click.pass_obj
def cleanup(obj: ContextObj, dry_run: bool):
    """
    Cleanup CLI
    """
    obj.dry_run = dry_run


def get_component_distfiles(component: QubesComponent):
    current_distfiles = []
    try:
        for file in (
            component.get_parameters().get("source", {}).get("files", [])
        ):
            distfile_fname = get_archive_name(file)
            if distfile_fname:
                current_distfiles.append(distfile_fname)

            if file.get("signature", None):
                current_distfiles.append(os.path.basename(file["signature"]))

    except ComponentError:
        pass

    return current_distfiles


@click.command()
@click.pass_obj
def distfiles(obj: ContextObj):
    """
    Cleanup previous distribution files versions.
    """
    for component in obj.components:
        current_distfiles = get_component_distfiles(component)

        if not (obj.config.distfiles_dir / component.name).exists():
            continue

        for file in (obj.config.distfiles_dir / component.name).iterdir():
            if file.name not in current_distfiles:
                if obj.dry_run:
                    click.secho(f"DRY-RUN: {file}")
                else:
                    click.secho(file)
                    file.unlink()


@click.command("build-artifacts")
@click.option(
    "--keep-versions", default=3, help="Number of old versions to keep."
)
@click.pass_obj
def build_artifacts(obj: ContextObj, keep_versions):
    """
    Cleanup old build artifacts.
    """
    for component in obj.components:
        component_dir = obj.config.artifacts_dir / "components" / component.name
        if not component_dir.exists():
            continue

        versions = sorted(
            [v for v in component_dir.iterdir() if v.name != "noversion"],
            reverse=True,
        )
        for version in versions[keep_versions:]:
            if obj.dry_run:
                click.secho(f"DRY-RUN: {version}")
            else:
                click.secho(version)
                shutil.rmtree(version)


@click.command()
@click.option(
    "--log-retention-days", default=30, help="Number of days to keep logs."
)
@click.pass_obj
def logs(obj: ContextObj, log_retention_days):
    """
    Cleanup old logs.
    """
    logs_dir = obj.config.logs_dir
    cutoff_date = datetime.now() - timedelta(days=log_retention_days)

    for log_file in logs_dir.iterdir():
        if (
            log_file.is_file()
            and datetime.fromtimestamp(log_file.stat().st_mtime) < cutoff_date
        ):
            if obj.dry_run:
                click.secho(f"DRY-RUN: {log_file}")
            else:
                click.secho(log_file)
                log_file.unlink()


@click.command()
@click.option(
    "--force",
    default=False,
    is_flag=True,
    help="Force temporary directory cleanup.",
)
@click.pass_obj
def tmp(obj: ContextObj, force: bool):
    """
    Cleanup temporary files and directories.
    """
    if not obj.config.temp_dir.exists():
        return
    for temp_dir in obj.config.temp_dir.iterdir():
        # remove empty directory only unless force
        if force or not list(temp_dir.iterdir()):
            if obj.dry_run:
                click.secho(f"DRY-RUN: {temp_dir}")
            else:
                click.secho(temp_dir)
                shutil.rmtree(temp_dir)


@click.command()
@click.option(
    "--all",
    default=False,
    is_flag=True,
    help="Cleanup all caches including chroot and installer.",
)
@click.option(
    "--chroot/--no-chroot",
    default=False,
    is_flag=True,
    help="Cleanup chroot cache.",
)
@click.option(
    "--chroot-only-unused",
    default=False,
    is_flag=True,
    help="Cleanup unused chroot cache.",
)
@click.option(
    "--installer/--no-installer",
    default=False,
    is_flag=True,
    help="Cleanup installer cache.",
)
@click.option(
    "--installer-chroot/--no-installer-chroot",
    default=False,
    is_flag=True,
    help="Cleanup installer chroot cache.",
)
@click.option(
    "--installer-templates/--no-installer-templates",
    default=False,
    is_flag=True,
    help="Cleanup installer templates cache.",
)
@click.pass_obj
def cache(
    obj: ContextObj,
    all: bool,
    chroot: bool,
    chroot_only_unused: bool,
    installer: bool,
    installer_chroot: bool,
    installer_templates: bool,
):
    """
    Cleanup cache files and directories.
    """
    if all:
        chroot = True
        installer = True

    to_delete = []
    if chroot:
        to_delete.append(obj.config.cache_dir / "chroot")
    if chroot_only_unused:
        distributions = [dist.name for dist in obj.distributions]
        for chroot_dir in (obj.config.cache_dir / "chroot").iterdir():
            if chroot_dir.name not in distributions:
                to_delete.append(chroot_dir)
    if installer:
        to_delete.append(obj.config.cache_dir / "installer")
    if installer_chroot:
        to_delete.append(obj.config.cache_dir / "installer" / "chroot" / "mock")
    if installer_templates:
        to_delete.append(obj.config.cache_dir / "installer" / "templates")

    for cache_dir in to_delete:
        if cache_dir.exists():
            if obj.dry_run:
                click.secho(f"DRY-RUN: {cache_dir}")
            else:
                click.secho(cache_dir)
                shutil.rmtree(cache_dir)


@click.command()
@click.option(
    "--keep-versions", default=3, help="Number of old versions to keep."
)
@click.option(
    "--log-retention-days", default=30, help="Number of days to keep logs."
)
@click.option(
    "--force-tmp",
    default=False,
    is_flag=True,
    help="Force temporary directory cleanup.",
)
@click.option(
    "--all-cache",
    default=False,
    is_flag=True,
    help="Cleanup all caches including chroot and installer.",
)
@click.option(
    "--chroot/--no-chroot",
    default=False,
    is_flag=True,
    help="Cleanup chroot cache.",
)
@click.option(
    "--installer/--no-installer",
    default=False,
    is_flag=True,
    help="Cleanup installer cache.",
)
@click.option(
    "--installer-chroot/--no-installer-chroot",
    default=False,
    is_flag=True,
    help="Cleanup installer chroot cache.",
)
@click.option(
    "--installer-templates/--no-installer-templates",
    default=False,
    is_flag=True,
    help="Cleanup installer templates cache.",
)
@click.pass_context
def all(
    ctx,
    keep_versions,
    log_retention_days,
    force_tmp,
    all_cache,
    chroot,
    installer,
    installer_chroot,
    installer_templates,
):
    """
    Cleanup all.
    """
    ctx.invoke(distfiles)
    ctx.invoke(build_artifacts, keep_versions=keep_versions)
    ctx.invoke(logs, log_retention_days=log_retention_days)
    ctx.invoke(tmp, force=force_tmp)
    ctx.invoke(
        cache,
        all=all_cache,
        chroot=chroot,
        installer=installer,
        installer_chroot=installer_chroot,
        installer_templates=installer_templates,
    )


cleanup.add_command(distfiles)
cleanup.add_command(build_artifacts)
cleanup.add_command(logs)
cleanup.add_command(tmp)
cleanup.add_command(cache)
cleanup.add_command(all)
