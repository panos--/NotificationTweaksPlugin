from trac.core import *
import re
from trac.env import IEnvironmentSetupParticipant
import trac.ticket.notification as note


class NotificationTweaksPluginSetupParticipant(Component):
    """ This component monkey patches note.TicketNotifyEmail.get_recipients so that trac will never 
    notify the person who updated the ticket about their own update"""
    implements(IEnvironmentSetupParticipant)

    def __init__(self):
        def log(msg, method):
            method('NotificationTweaksPlugin: %s' % msg)

        def log_debug(msg):
            log(msg, self.log.debug)

        def is_enabled():
            return self.compmgr.enabled[self.__class__]

        if is_enabled():
            log_debug('enabled')
        else:
            log_debug('disabled')

        log_debug('initializing')

        # only if we should be enabled do we monkey patch
        old_get_recipients = note.TicketNotifyEmail.get_recipients

        def new_get_recipients(self, tktid):
            def log_debug(msg):
                log(msg, self.env.log.debug)

            cursor = self.db.cursor()

            def notify_comments_only(torecipients, ccrecipients):
                default_domain = self.env.config.get("notification", "smtp_default_domain")

                cursor.execute("SELECT time FROM ticket_change WHERE ticket = %s "
                               "ORDER BY time DESC LIMIT 1", (tktid,))
                time = None
                for time, in cursor:
                    break
                if time is None:
                    log_debug('Error: No ticket change found for ticket')
                    return torecipients, ccrecipients

                cursor.execute("SELECT ticket FROM ticket_change "
                               " WHERE ticket = %s AND time = %s "
                               "   AND (field = 'description' "
                               "        OR (field = 'comment' and newvalue != ''))"
                               " LIMIT 1",
                    (tktid, time))
                has_comment = None
                for has_comment, in cursor: break
                if not has_comment is None:
                    log_debug('ticket change has comment, notifying all recipients')
                    return torecipients, ccrecipients

                def get_comment_only_addresses(default_domain):
                    subjects = self.env.config.getlist('notification', 'comments_only_rcpts')
                    return [subject_to_email(subject, default_domain)
                            for subject in subjects]

                def subject_to_email(subject, default_domain):
                    if '@' in subject:
                        return subject

                    cursor = self.db.cursor()
                    cursor.execute("SELECT value FROM session_attribute "
                                   "WHERE name = 'email' AND sid = %s", (subject,))
                    email = None
                    for email, in cursor:
                        break

                    if not email is None:
                        return email

                    return subject + '@' + default_domain

                def recipient_to_email(recipient, default_domain):
                    match = re.search(r"<\s*(.+)\s*>", recipient)
                    if not match is None:
                        recipient = match.group(1)
                    if not '@' in recipient:
                        recipient = subject_to_email(recipient, default_domain)
                    return recipient

                cursor.execute("SELECT owner FROM ticket WHERE id = %s", (tktid,))
                owner = None
                for owner, in cursor:
                    break

                owner_addr = subject_to_email(owner, default_domain)
                def is_owner(address):
                    return address == owner_addr

                comment_only_addresses =\
                    [addr for addr in get_comment_only_addresses(default_domain) if not is_owner(addr)]
                log_debug('comment_only_addresses = %s' % comment_only_addresses)

                def skip(recipient):
                    rcpt_email = recipient_to_email(recipient, default_domain)
                    log_debug('check address %s' % rcpt_email)

                    found = rcpt_email in comment_only_addresses
                    if found:
                        log_debug('skip %s' % rcpt_email)
                    return found

                torecipients = [r for r in torecipients if not skip(r)]
                ccrecipients = [r for r in ccrecipients if not skip(r)]

                return torecipients, ccrecipients

            # From the NeverNotifyUpdater (v0.0.9) plugin by Russ Tyndall at Acceleration.net.
            # Original version can be found at http://www.trac-hacks.org/wiki/NeverNotifyUpdaterPlugin.
            def never_notify_updater(torecipients, ccrecipients):
                if not self.env.config.getbool('notification', 'never_notify_updater'):
                    log_debug('never_notify_updater disabled in config - leaving recipients untouched')
                    return torecipients, ccrecipients

                defaultDomain = self.env.config.get("notification", "smtp_default_domain")
                domain = ''
                if defaultDomain: domain = '@' + defaultDomain

                cursor = self.db.cursor()
                # Suppress the updater from the recipients
                updater = None
                up_em = None
                cursor.execute("SELECT author FROM ticket_change WHERE ticket=%s "
                               "ORDER BY time DESC LIMIT 1", (tktid,))
                for updater, in cursor: break
                else:
                    cursor.execute("SELECT reporter FROM ticket WHERE id=%s",
                        (tktid,))
                    for updater, in cursor: break

                cursor.execute("SELECT value FROM session_attribute WHERE name='email' and sid=%s;", (updater,))
                for up_em, in cursor: break

                def finder(r):
                    if not r:
                        return None
                    log_debug('testing recipient %s to see if they are the updater %s'\
                              % ([r, r + domain], [updater, up_em, updater + domain]))
                    regexp = "<\s*%s(%s)?\s*>" % (r, domain)
                    rtn = (updater == r
                           or updater == r + domain
                           or updater + domain == r
                           or updater + domain == r + domain
                           # user prefs email
                           or up_em == r
                           or up_em == r + domain
                           # handles names followed by emails
                           or re.findall(regexp, updater)
                           or re.findall(regexp, updater + domain))
                    if rtn:
                        log_debug('blocking recipient %s' % r)
                        return rtn

                torecipients = [r for r in torecipients if not finder(r)]
                ccrecipients = [r for r in ccrecipients if not finder(r)]

                return torecipients, ccrecipients

            def always_cc(torecipients, ccrecipients):
                ccs = self.env.config.getlist('notification', 'always_cc')
                ccrecipients.extend(ccs)
                return torecipients, ccrecipients

            (torecipients, ccrecipients) = old_get_recipients(self, tktid)

            log_debug('Ticket %s: original recipients: to=%s, cc=%s' % (tktid, torecipients, ccrecipients))
            (torecipients, ccrecipients) = always_cc(torecipients, ccrecipients)
            log_debug('Ticket %s: always_cc: to=%s, cc=%s' % (tktid, torecipients, ccrecipients))
            (torecipients, ccrecipients) = never_notify_updater(torecipients, ccrecipients)
            log_debug('Ticket %s: never_notify_updater: to=%s, cc=%s' % (tktid, torecipients, ccrecipients))
            (torecipients, ccrecipients) = notify_comments_only(torecipients, ccrecipients)
            log_debug('Ticket %s: notify_comments_only: to=%s, cc=%s' % (tktid, torecipients, ccrecipients))


            log_debug('Ticket %s: final recipients: to=%s, cc=%s' % (tktid, torecipients, ccrecipients))

            return torecipients, ccrecipients

        if is_enabled():
            note.TicketNotifyEmail.get_recipients = new_get_recipients


    def environment_created(self):
        pass

    def environment_needs_upgrade(self, db):
        pass

    def upgrade_environment(self, db):
        pass




