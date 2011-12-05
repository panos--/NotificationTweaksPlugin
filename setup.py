from setuptools import setup

PACKAGE = 'notificationtweaks'

setup(name=PACKAGE,
      version='0.0.1',
      packages=[PACKAGE],
      url='http://www.trac-hacks.org/wiki/NotificationTweaksPlugin',
      license='http://www.opensource.org/licenses/mit-license.php',
      author='Thomas Weiss, based on work by Russ Tyndall at Acceleration.net',
      author_email='weiss@advanced.info',
      long_description="""
      Only send ticket notification emails with comments or description changes.
      """,
      entry_points={'trac.plugins': '%s = %s' % (PACKAGE, PACKAGE)},
)

