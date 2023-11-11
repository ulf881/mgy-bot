"""
    Prepara argumentos e banner do programa
"""
import logging
from utils import __version__, __program__, __author__, __email__

log = logging.getLogger("cmdline")


def banner():
    """
    Exibe banner ao rodar o programa
    Editar ASCII art em: http://patorjk.com/software/taag/#p=display&f=Doom&t=discord
    """
    log.debug("Exibindo banner para %s ver %s", __program__, __version__)
    print(__program__ + " v" + __version__, end="")
    print(
        r"""
     _ _                       _ 
    | (_)                     | |
  __| |_ ___  ___ ___  _ __ __| |
 / _` | / __|/ __/ _ \| '__/ _` |
| (_| | \__ \ (_| (_) | | | (_| |
 \__,_|_|___/\___\___/|_|  \__,_|
"""
    )
    print("Author: " + __author__ + " Email: " + __email__)
