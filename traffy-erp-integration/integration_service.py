"""
 Copyright (C) 2021 Falk Seidl <hi@falsei.de>

 Author: Falk Seidl <hi@falsei.de>

 This program is free software; you can redistribute it and/or
 modify it under the terms of the GNU General Public License as
 published by the Free Software Foundation; either version 2 of the
 License, or (at your option) any later version.

 This program is distributed in the hope that it will be useful, but
 WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with this program; if not, see <http://www.gnu.org/licenses/>.
"""
import database_manager
import pyaes
import codecs
import config
from models import ERPMaster, IdentityUpdate, TraffyDormitory, TraffyIdentity


def decrypt_data(data):
    if data is None:
        return None

    unhex = codecs.decode(data, "hex")
    decrypter = pyaes.Decrypter(pyaes.AESModeOfOperationCBC(config.DECRYPTION_KEY_STRING.encode(),
                                                            config.DECRYPTION_INIT_VECTOR))
    decrypted_data = decrypter.feed(unhex)
    try:
        decrypted_data += decrypter.feed()
    except ValueError:
        decrypted_data = data.encode()

    return codecs.decode(decrypted_data, config.REMOTE_CHARSET)


class IntegrationService:
    db_traffy = NotImplemented
    db_erp = NotImplemented

    def __init__(self):
        self.db_traffy = database_manager.DatabaseManagerTraffy()
        self.db_erp = database_manager.DatabaseManagerERP()

    def run_service(self):
        self.__clear_identity_updates_table()

        erp_session = self.db_erp.create_session()
        erp_master_data_query = erp_session.query(ERPMaster).all()

        traffy_session = self.db_traffy.create_session()

        for erp_row in erp_master_data_query:
            erp_debitor_id = erp_row.debitor_id
            erp_first_name = decrypt_data(erp_row.first_name)
            erp_last_name = decrypt_data(erp_row.last_name)
            erp_mail = decrypt_data(erp_row.mail)
            erp_dormitory_id = erp_row.dormitory_id
            erp_room = erp_row.room
            erp_ib_needed = erp_row.ib_needed
            erp_ib_expiry_date = erp_row.ib_expiry_date
            erp_contract_expiry_date = erp_row.contract_expiry_date

            if erp_ib_needed == "J":
                erp_ib_needed = True
            else:
                erp_ib_needed = False

            traffy_identity_query = traffy_session.query(TraffyIdentity).filter_by(customer_id=erp_debitor_id).all()

            traffy_identity_updated = False
            if len(traffy_identity_query) > 0:
                for traffy_identity in traffy_identity_query:
                    if traffy_identity.first_name != erp_first_name or \
                            traffy_identity.last_name != erp_last_name or \
                            traffy_identity.mail != erp_mail or \
                            traffy_session.query(TraffyDormitory).filter_by(
                                id=traffy_identity.dormitory_id).first() != erp_dormitory_id or \
                            traffy_identity.room != erp_room:
                        traffy_identity_updated = True

                    if erp_dormitory_id not in config.RELEVANT_DORMITORY_IDS:
                        self.__mark_identity_as_deletable(traffy_identity.id, traffy_identity.customer_id)
                        continue

                    if traffy_identity_updated is True:
                        self.__mark_identity_as_updatable(traffy_identity.id,
                                                          erp_debitor_id,
                                                          traffy_identity.customer_id,
                                                          erp_first_name,
                                                          erp_last_name,
                                                          erp_mail,
                                                          erp_dormitory_id,
                                                          erp_room,
                                                          erp_ib_needed,
                                                          erp_ib_expiry_date,
                                                          erp_contract_expiry_date)
            else:
                if erp_dormitory_id not in config.RELEVANT_DORMITORY_IDS:
                    continue

                if erp_first_name is not None and erp_last_name is not None:
                    if "Baublockierung" in erp_first_name or \
                            "Baublockierung" in erp_last_name:
                        continue

                self.__mark_identity_as_updatable(None,
                                                  erp_debitor_id,
                                                  None,
                                                  erp_first_name,
                                                  erp_last_name,
                                                  erp_mail,
                                                  erp_dormitory_id,
                                                  erp_room,
                                                  erp_ib_needed,
                                                  erp_ib_expiry_date,
                                                  erp_contract_expiry_date)

        traffy_master_data_query = traffy_session.query(TraffyIdentity).all()
        for traffy_row in traffy_master_data_query:
            traffy_customer_id = traffy_row.customer_id

            erp_identity_query = erp_session.query(ERPMaster).filter_by(debitor_id=traffy_row.customer_id).all()

            if len(erp_identity_query) == 0:
                self.__mark_identity_as_deletable(traffy_row.id, traffy_row.customer_id)

        traffy_session.close()
        erp_session.close()

    def __mark_identity_as_updatable(self, identity_id, new_customer_id, old_customer_id, first_name, last_name,
                                     mail, dormitory_id, room, ib_needed, ib_expiry_date, contract_expiry_date):
        print(new_customer_id)
        traffy_session = self.db_traffy.create_session()
        try:
            row = IdentityUpdate(identity_id=identity_id,
                                 new_customer_id=new_customer_id,
                                 old_customer_id=old_customer_id,
                                 first_name=first_name,
                                 last_name=last_name,
                                 mail=mail,
                                 dormitory_id=dormitory_id,
                                 room=room,
                                 ib_needed=ib_needed,
                                 ib_expiry_date=ib_expiry_date,
                                 contract_expiry_date=contract_expiry_date)
            traffy_session.add(row)
            traffy_session.commit()
        except Exception as ex:
            import traceback
            traceback.print_exc()
            traffy_session.rollback()
        finally:
            #traffy_session.close()
            pass

    def __mark_identity_as_deletable(self, identity_id, customer_id):
        self.__mark_identity_as_updatable(identity_id,
                                          None,
                                          customer_id,
                                          None,
                                          None,
                                          None,
                                          None,
                                          None,
                                          None,
                                          None,
                                          None)

    def __clear_identity_updates_table(self):
        traffy_session = self.db_traffy.create_session()

        try:
            traffy_session.query(IdentityUpdate).delete()
            traffy_session.commit()
        except:
            traffy_session.rollback()
        finally:
            #traffy_session.close()
            pass


integration_service = IntegrationService()
integration_service.run_service()
