import datetime
import logging
import logging.config

from qubesbuilder.exc import QubesBuilderError


class DefaultFormatter(logging.Formatter):
    def __init__(
        self, fmt="%(asctime)s [%(name)s] %(message)s", *args, **kwargs
    ):
        super().__init__(fmt, *args, **kwargs)


class ConsoleFormatter(logging.Formatter):
    """
    A formatter that colors messages in console.
    """

    default_time_format = "%H:%M:%S"
    # https://en.wikipedia.org/wiki/ANSI_escape_code
    colors = {
        "grey": "\x1b[38;5;246m",
        "green": "\x1b[32m",
        "yellow": "\x1b[93;1m",
        "red": "\x1b[91;1m",
        "cyan": "\x1b[96m",
        "reset": "\x1b[0m",
    }

    def __init__(self, fmt=None, *args, **kwargs):
        if fmt is None:
            fmt = (
                "{grey}%(asctime)s "
                "{cyan}[%(name)s] "
                "$COLOR%(message)s"
                "{reset}"
            ).format(**self.colors)
        super().__init__(fmt, *args, **kwargs)

    def format(self, record):
        result = super().format(record)
        level_color = {
            "DEBUG": "grey",
            "INFO": "reset",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red",
        }.get(record.levelname, "reset")
        result = result.replace("$COLOR", self.colors[level_color])
        return result

    def formatException(self, ei):
        result = super().formatException(ei)
        return "{red}{result}{reset}".format(result=result, **self.colors)


def create_file_handler(log_file):
    file_handler = logging.FileHandler(log_file, mode="w")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(DefaultFormatter())
    return file_handler


def create_console_handler(verbose):
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(ConsoleFormatter())
    return console_handler


def get_logger_name(name, plugin):
    fname = []
    if hasattr(plugin, "component"):
        fname.append(plugin.component.name)
    if hasattr(plugin, "dist") and not hasattr(plugin, "template"):
        fname.append(plugin.dist.distribution)
    if hasattr(plugin, "template"):
        fname.append(plugin.template.name)
    return ".".join([name] + fname)


def get_log_filename(plugin, logs_dir):
    fname = [QubesBuilderTimeStamp]
    if hasattr(plugin, "component"):
        fname.append(plugin.component.name)
    if hasattr(plugin, "dist") and not hasattr(plugin, "template"):
        fname.append(plugin.dist.distribution)
    if hasattr(plugin, "template"):
        fname.append(plugin.template.name)
    log_fname = "-".join(fname)
    return (logs_dir / log_fname).with_suffix(".log")


def get_logger(name, plugin=None):
    if plugin:
        logger = QubesBuilderLogger.getChild(get_logger_name(name, plugin))
        try:
            logs_dir = plugin.config.logs_dir
            logs_dir.mkdir(parents=True, exist_ok=True)
            log_file = get_log_filename(plugin, logs_dir)

            file_handler = create_file_handler(log_file)
            console_handler = create_console_handler(plugin.config.verbose)

            logger.addHandler(file_handler)
            logger.addHandler(console_handler)
            logger.propagate = False

            logger.info(f"Log file: {log_file}")
        except OSError as e:
            raise QubesBuilderError("Failed to initialize logging file") from e
    else:
        logger = QubesBuilderLogger.getChild(name)
    return logger


def init_logger(verbose=False):
    QubesBuilderLogger.setLevel(logging.DEBUG)
    QubesBuilderLogger.propagate = False
    QubesBuilderLogger.addHandler(create_console_handler(verbose))


QubesBuilderLogger = logging.getLogger("qb")
QubesBuilderTimeStamp = datetime.datetime.now(datetime.UTC).strftime(
    "%Y%m%d%H%M%S"
)
