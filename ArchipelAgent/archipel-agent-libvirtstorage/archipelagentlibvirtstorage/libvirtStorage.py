# -*- coding: utf-8 -*-
#
# libvirtStorage.py
#
# Copyright (C) 2010 Antoine Mercadal <antoine.mercadal@inframonde.eu>
# This file is part of ArchipelProject
# http://archipelproject.org
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import subprocess
import xmpp
import libvirt

from archipelcore.archipelPlugin import TNArchipelPlugin
from archipel.archipelVirtualMachine import ARCHIPEL_ERROR_CODE_VM_MIGRATING
from archipelcore.utils import build_error_iq


ARCHIPEL_NS_STORAGE_POOL                        = "archipel:storage:pool"
ARCHIPEL_NS_STORAGE_VOLUME                      = "archipel:storage:volume"

ARCHIPEL_ERROR_CODE_STORAGE_POOL_LIST           = -11001
ARCHIPEL_ERROR_CODE_STORAGE_POOL_CREATE         = -11002
ARCHIPEL_ERROR_CODE_STORAGE_POOL_DESTROY        = -11003
ARCHIPEL_ERROR_CODE_STORAGE_POOL_INFO           = -11004
ARCHIPEL_ERROR_CODE_STORAGE_POOL_DELETE         = -11005
ARCHIPEL_ERROR_CODE_STORAGE_POOL_DEFINE         = -11006
ARCHIPEL_ERROR_CODE_STORAGE_POOL_UNDEFINE       = -11007
ARCHIPEL_ERROR_CODE_STORAGE_POOL_DESCRIPTION    = -11008

ARCHIPEL_ERROR_CODE_STORAGE_VOLUME_DEFINE       = -11009
ARCHIPEL_ERROR_CODE_STORAGE_VOLUME_UNDEFINE     = -11010
ARCHIPEL_ERROR_CODE_STORAGE_VOLUME_DESCRIPTION  = -11011
ARCHIPEL_ERROR_CODE_STORAGE_VOLUME_INFO         = -11012



class TNLibvirtStorageManagement (TNArchipelPlugin):
    """
    Plugin that manages the libvirt storage API
    """

    def __init__(self, configuration, entity, entry_point_group):
        """
        Initialize the plugin.
        @type configuration: Configuration object
        @param configuration: the configuration
        @type entity: L{TNArchipelEntity}
        @param entity: the entity that owns the plugin
        @type entry_point_group: string
        @param entry_point_group: the group name of plugin entry_point
        """
        TNArchipelPlugin.__init__(self, configuration=configuration, entity=entity, entry_point_group=entry_point_group)

        # permissions
        self.entity.permission_center.create_permission("storage_poollist", "Authorizes user to get list existing pools", False)
        self.entity.permission_center.create_permission("storage_poolinfo", "Authorizes user to get information about pools", False)
        self.entity.permission_center.create_permission("storage_poolcreate", "Authorizes user to create pools", False)
        self.entity.permission_center.create_permission("storage_pooldescription", "Authorizes user to get XML description of pools", False)
        self.entity.permission_center.create_permission("storage_pooldefine", "Authorizes user to define new pools", False)
        self.entity.permission_center.create_permission("storage_poolundefine", "Authorizes user to undefine pools", False)
        self.entity.permission_center.create_permission("storage_poolautostart", "Authorizes user to set pool's autostart", False)

        self.entity.permission_center.create_permission("storage_volumeinfo", "Authorizes user to get volume information", False)
        self.entity.permission_center.create_permission("storage_volumedefine", "Authorizes user to define new volumes", False)
        self.entity.permission_center.create_permission("storage_volumedescription", "Authorizes user to get XML description of volumes", False)
        self.entity.permission_center.create_permission("storage_volumeundefine", "Authorizes user to undefine volumes", False)


    ### Plugin interface

    def register_handlers(self):
        """
        This method will be called by the plugin user when it will be
        necessary to register module for listening to stanza.
        """
        self.entity.xmppclient.RegisterHandler('iq', self.process_iq_pool, ns=ARCHIPEL_NS_STORAGE_POOL)
        self.entity.xmppclient.RegisterHandler('iq', self.process_iq_volume, ns=ARCHIPEL_NS_STORAGE_VOLUME)

    def unregister_handlers(self):
        """
        Unregister the handlers.
        """
        self.entity.xmppclient.UnregisterHandler('iq', self.process_iq_pool, ns=ARCHIPEL_NS_STORAGE_POOL)
        self.entity.xmppclient.UnregisterHandler('iq', self.process_iq_volume, ns=ARCHIPEL_NS_STORAGE_VOLUME)

    @staticmethod
    def plugin_info():
        """
        Return informations about the plugin.
        @rtype: dict
        @return: dictionary contaning plugin informations
        """
        plugin_friendly_name           = "Libvirt Storage"
        plugin_identifier              = "libvirtstorage"
        plugin_configuration_section   = None
        plugin_configuration_tokens    = []

        return {    "common-name"               : plugin_friendly_name,
                    "identifier"                : plugin_identifier,
                    "configuration-section"     : plugin_configuration_section,
                    "configuration-tokens"      : plugin_configuration_tokens }


    ### Libvirt Pools

    def pool_list(self):
        """
        return a list of names of existing pools
        @rtype: array
        @return: array of all pool names
        """
        return self.entity.libvirt_connection.listDefinedStoragePools()

    def pool_get(self, identifier):
        """
        return information about a given pool
        @type identifier: string
        @param identifier: UUID or Name
        @rtype: virStoragePool
        @return: the current storage pool
        """
        try:
            pool = self.entity.libvirt_connection.storagePoolLookupByName(identifier)
        except libvirt.libvirtError:
            try:
                pool = self.entity.libvirt_connection.storagePoolLookupByUUID(identifier)
            except libvirt.libvirtError:
                raise Exception("Pool with identifier %s not found" % identifier)
        return pool

    def pool_info(self, identifier):
        """
        Return the given pool info
        @type identifier: string
        @param identifier: UUID or name
        @rtype: dict
        @return: dict containing state, capacity, allocation and availability
        """
        pool = self.pool_get(identifier)
        state, capacity, allocation, available = pool.info()
        persistant = pool.isPersistent()
        autostart = pool.autostart()
        volumeCount = pool.numOfVolumes()
        return {"state": state,
                "capacity": capacity,
                "allocation": allocation,
                "available": available,
                "persistant": persistant,
                "autostart": autostart,
                "volumecount": volumeCount}

    def pool_list_volumes(self, identifier):
        """
        Return all the volumes in a given pool
        @type identifier: string
        @param identifier: UUID or name
        @rtype: array
        @return: array of all volume names
        """
        pool = self.pool_get(identifier)
        return pool.listVolumes()

    def pool_create(self, identifier):
        """
        Create (start) the given pool
        @type identifier: string
        @param identifier: UUID or name
        @rtype: int
        @return: result of libvirt function
        """
        pool = self.pool_get(identifier)
        ret = pool.create(0)
        self.entity.push_change("storage:pool", "created")
        return ret

    def pool_destroy(self, identifier):
        """
        Destroy (stop) the given pool
        @type identifier: string
        @param identifier: UUID or name
        @rtype: int
        @return: result of libvirt function
        """
        pool = self.pool_get(identifier)
        ret = pool.destroy()
        self.entity.push_change("storage:pool", "destroyed")
        return ret

    def pool_xmldesc(self, identifier):
        """
        Return the XML description of the given pool
        @type identifier: string
        @param identifier: UUID or name
        @rtype: xmpp.Node
        @return: the pool's description
        """
        pool = self.pool_get(identifier)
        return xmpp.simplexml.NodeBuilder(data=str(pool.XMLDesc(0))).getDom()

    def pool_define(self, xmldesc, build=True):
        """
        Define a new stroage pool
        @type xmldesc: xmpp.Node
        @param xmldesc: the XML description
        @rtype: virStoragePool
        @return: the new storage pool
        """
        is_update = False
        existing_pool = None
        old_autostart = False
        try:
            identifier = xmldesc.getTag("name").getData()
            existing_pool = self.pool_get(identifier)
            old_autostart = existing_pool.autostart()
        except:
            pass
        if existing_pool:
            if not existing_pool.isActive():
                self.pool_undefine(identifier, delete=False)
                is_update = True
            else:
                raise Exception("You cannot update an active pool. Please stop it first.")
        xmlString = str(xmldesc).replace('xmlns="http://www.gajim.org/xmlns/undeclared" ', '')
        pool = self.entity.libvirt_connection.storagePoolDefineXML(xmlString, 0)
        if build:
            pool.build(0)
        if is_update:
            pool.setAutostart(old_autostart)
        self.entity.push_change("storage:pool", "defined")
        return pool

    def pool_undefine(self, identifier, delete=True):
        """
        Undefine a new storage pool
        @type identifier: string
        @param identifier: UUID or name
        @rtype: int
        @return: result of libvirt function
        """
        pool = self.pool_get(identifier)
        if pool.isActive():
            self.pool_destroy(identifier)
        if delete:
            try:
                pool.delete(0)
            except:
                pass
        ret = pool.undefine()
        self.entity.push_change("storage:pool", "undefined")
        return ret

    def pool_setautostart(self, identifier, autostart):
        """
        Set if the pool is in autostart mode
        @type identifier: string
        @param identifier: UUID or name
        @type autostart: Bool
        @param autostart: define if pool should start with host
        @rtype: int
        @return: result of libvirt function
        """
        pool = self.pool_get(identifier)
        ret = pool.setAutostart(autostart)
        self.entity.push_change("storage:pool", "autostart")
        return ret


    ### Libvirt Volumes

    def volume_get(self, pool_identifier, identifier):
        """
        Get the volume with given identifier in given storage pool
        @type pool_identifier: string
        @param pool_identifier: UUID or name of the pool
        @type identifier: string
        @param identifier: Name of the volume
        @rtype: virStorageVol
        @return: the volume
        """
        pool = self.pool_get(pool_identifier)
        volume = pool.storageVolLookupByName(identifier)
        return volume

    def volume_info(self, pool_identifier, identifier):
        """
        Get the volume information
        @type pool_identifier: string
        @param pool_identifier: UUID or name of the pool
        @type identifier: string
        @param identifier: Name of the volume
        @rtype: virStorageVol
        @return: the volume
        """
        volume = self.volume_get(pool_identifier, identifier)
        typ, capacity, allocation = volume.info()
        path = volume.path()
        name = volume.name()
        key = volume.key()
        return {"name": name,
                "type": typ,
                "capacity": capacity,
                "allocation": allocation,
                "path": path,
                "key": key}

    def volume_define(self, pool_identifier, xmldesc):
        """
        Define a new volume in given pool
        @type pool_identifier: string
        @param pool_identifier: UUID or name of the pool
        @type xmldesc: xmpp.Node
        @param xmldesc: the description of the volume to create
        """
        pool = self.pool_get(pool_identifier)
        xmlString = str(xmldesc).replace('xmlns="http://www.gajim.org/xmlns/undeclared" ', '')
        volume = pool.createXML(xmlString, 0)
        self.entity.push_change("storage:volume", "defined")
        return volume

    def volume_xmldesc(self, pool_identifier, identifier):
        """
        Return the XML description of the given pool
        @type pool_identifier: string
        @param pool_identifier: UUID or name of the pool
        @type identifier: string
        @param identifier: Name of the volume
        @rtype: xmpp.Node
        @return: the volume's description
        """
        volume = self.volume_get(pool_identifier, identifier)
        return xmpp.simplexml.NodeBuilder(data=str(volume.XMLDesc(0))).getDom()

    def volume_undefine(self, pool_identifier, identifier):
        """
        Undefine a storage volume
        @type pool_identifier: string
        @param pool_identifier: UUID or name of the pool
        @type identifier: string
        @param identifier: Name of volume
        @rtype: int
        @return: result of libvirt function
        """
        volume = self.volume_get(pool_identifier, identifier)
        ret = volume.delete(0)
        self.entity.push_change("storage:volume", "undefined")
        return ret


    ### XMPP Pool Processing

    def process_iq_pool(self, conn, iq):
        """
        Invoked when new ARCHIPEL_NS_STORAGE_POOL IQ is received.
        It understands IQ of type:
            - poollist
            - poolinfo
            - poolcreate
            - pooldestroy
            - pooldescription
            - pooldefine
            - poolundefine
            - poolautostart
        @type conn: xmpp.Dispatcher
        @param conn: ths instance of the current connection that send the message
        @type iq: xmpp.Protocol.Iq
        @param iq: the received IQ
        """
        reply = None
        action = self.entity.check_acp(conn, iq)
        self.entity.check_perm(conn, iq, action, -1, prefix="storage_")
        if action == "poollist":
            reply = self.iq_poollist(iq)
        elif action == "poolinfo":
            reply = self.iq_poolinfo(iq)
        elif action == "poolcreate":
            reply = self.iq_poolcreate(iq)
        elif action == "pooldestroy":
            reply = self.iq_pooldestroy(iq)
        elif action == "pooldescription":
            reply = self.iq_pooldescription(iq)
        elif action == "pooldefine":
            reply = self.iq_pooldefine(iq)
        elif action == "poolundefine":
            reply = self.iq_poolundefine(iq)
        elif action == "poolsetautostart":
            reply = self.iq_poolsetautostart(iq)
        if reply:
            conn.send(reply)
            raise xmpp.protocol.NodeProcessed

    def iq_poollist(self, iq):
        """
        List all available pools
        @type iq: xmpp.Protocol.Iq
        @param iq: the received IQ
        @rtype: xmpp.Protocol.Iq
        @return: a ready to send IQ containing the result of the action
        """
        try:
            reply = iq.buildReply("result")
            poolNodes = [];
            for poolName in self.pool_list():
                poolNode = xmpp.Node("pool")
                poolNode.setData(poolName)
                poolNodes.append(poolNode)
            reply.setQueryPayload(poolNodes)
        except Exception as ex:
            reply = build_error_iq(self, ex, iq, ARCHIPEL_ERROR_CODE_STORAGE_POOL_LIST)
        return reply

    def iq_poolinfo(self, iq):
        """
        get info of a given pool
        @type iq: xmpp.Protocol.Iq
        @param iq: the received IQ
        @rtype: xmpp.Protocol.Iq
        @return: a ready to send IQ containing the result of the action
        """
        try:
            reply = iq.buildReply("result")
            identifier = iq.getTag("query").getTag("archipel").getAttr("identifier")
            pool = self.pool_get(identifier)
            poolInfo = self.pool_info(identifier)
            infoNode = xmpp.Node("info", attrs=poolInfo)
            volumeNodes = xmpp.Node("volumes")
            for volumeName in self.pool_list_volumes(identifier):
                volumeNodes.addChild("volume", attrs={"name": volumeName})
            reply.setQueryPayload([infoNode, volumeNodes])
        except Exception as ex:
            reply = build_error_iq(self, ex, iq, ARCHIPEL_ERROR_CODE_STORAGE_POOL_INFO)
        return reply

    def iq_poolcreate(self, iq):
        """
        Create a new storage pool
        @type iq: xmpp.Protocol.Iq
        @param iq: the received IQ
        @rtype: xmpp.Protocol.Iq
        @return: a ready to send IQ containing the result of the action
        """
        try:
            reply = iq.buildReply("result")
            identifier = iq.getTag("query").getTag("archipel").getAttr("identifier")
            self.pool_create(identifier)
            self.entity.shout("storagepool", "I just started the pool named %s as asked by %s" % (identifier, iq.getFrom().getNode()))
        except Exception as ex:
            reply = build_error_iq(self, ex, iq, ARCHIPEL_ERROR_CODE_STORAGE_POOL_CREATE)
        return reply

    def iq_pooldestroy(self, iq):
        """
        Destroy an existing storage pool
        @type iq: xmpp.Protocol.Iq
        @param iq: the received IQ
        @rtype: xmpp.Protocol.Iq
        @return: a ready to send IQ containing the result of the action
        """
        try:
            reply = iq.buildReply("result")
            identifier = iq.getTag("query").getTag("archipel").getAttr("identifier")
            self.pool_destroy(identifier)
            self.entity.shout("storagepool", "I just destroyed the pool named %s as asked by %s" % (identifier, iq.getFrom().getNode()))
        except Exception as ex:
            reply = build_error_iq(self, ex, iq, ARCHIPEL_ERROR_CODE_STORAGE_POOL_DESTROY)
        return reply

    def iq_pooldescription(self, iq):
        """
        Return the XML description of a pool
        @type iq: xmpp.Protocol.Iq
        @param iq: the received IQ
        @rtype: xmpp.Protocol.Iq
        @return: a ready to send IQ containing the result of the action
        """
        try:
            reply = iq.buildReply("result")
            identifier = iq.getTag("query").getTag("archipel").getAttr("identifier")
            description = self.pool_xmldesc(identifier)
            reply.setQueryPayload([description])
        except Exception as ex:
            reply = build_error_iq(self, ex, iq, ARCHIPEL_ERROR_CODE_STORAGE_POOL_DESCRIPTION)
        return reply

    def iq_pooldefine(self, iq):
        """
        Define a new stroage pool
        @type iq: xmpp.Protocol.Iq
        @param iq: the received IQ
        @rtype: xmpp.Protocol.Iq
        @return: a ready to send IQ containing the result of the action
        """
        try:
            reply = iq.buildReply("result")
            xmldesc = iq.getTag("query").getTag("archipel").getTag("pool")
            autobuild = iq.getTag("query").getTag("archipel").getAttr("build").lower()
            if autobuild == "true":
                autobuild = True
            else:
                autobuild = False
            pool = self.pool_define(xmldesc, build=autobuild)
            self.entity.shout("storagepool", "I just defined a new pool named %s as asked by %s" % (pool.name(), iq.getFrom().getNode()))
        except Exception as ex:
            reply = build_error_iq(self, ex, iq, ARCHIPEL_ERROR_CODE_STORAGE_POOL_DEFINE)
        return reply

    def iq_poolundefine(self, iq):
        """
        Undefine a new stroage pool
        @type iq: xmpp.Protocol.Iq
        @param iq: the received IQ
        @rtype: xmpp.Protocol.Iq
        @return: a ready to send IQ containing the result of the action
        """
        try:
            reply = iq.buildReply("result")
            identifier = iq.getTag("query").getTag("archipel").getAttr("identifier")
            autodelete = iq.getTag("query").getTag("archipel").getAttr("delete").lower()
            if autodelete == "true":
                autodelete = True
            else:
                autodelete = False
            self.pool_undefine(identifier, delete=autodelete)
            self.entity.shout("storagepool", "I just undefined the pool named %s as asked by %s" % (identifier, iq.getFrom().getNode()))
        except Exception as ex:
            reply = build_error_iq(self, ex, iq, ARCHIPEL_ERROR_CODE_STORAGE_POOL_UNDEFINE)
        return reply

    def iq_poolsetautostart(self, iq):
        """
        Set the value of a pool's autostart
        @type iq: xmpp.Protocol.Iq
        @param iq: the received IQ
        @rtype: xmpp.Protocol.Iq
        @return: a ready to send IQ containing the result of the action
        """
        try:
            reply = iq.buildReply("result")
            identifier = iq.getTag("query").getTag("archipel").getAttr("identifier")
            autostart = iq.getTag("query").getTag("archipel").getAttr("autostart").lower()
            if autostart == "true":
                autostart = True
            else:
                autostart = False
            self.pool_setautostart(identifier, autostart)
            self.entity.shout("storagepool", "I just set the autostart to %s for the pool named %s as asked by %s" % (str(autostart), identifier, iq.getFrom().getNode()))
        except Exception as ex:
            reply = build_error_iq(self, ex, iq, ARCHIPEL_ERROR_CODE_STORAGE_POOL_UNDEFINE)
        return reply


    ### XMPP Volume Processing

    def process_iq_volume(self, conn, iq):
        """
        Invoked when new ARCHIPEL_NS_STORAGE_VOLUME IQ is received.
        It understands IQ of type:
            - volumeinfo
            - volumedefine
            - volumedescription
            - volumeundefine
        @type conn: xmpp.Dispatcher
        @param conn: ths instance of the current connection that send the message
        @type iq: xmpp.Protocol.Iq
        @param iq: the received IQ
        """
        reply = None
        action = self.entity.check_acp(conn, iq)
        self.entity.check_perm(conn, iq, action, -1, prefix="storage_")
        if action == "volumeinfo":
            reply = self.iq_volumeinfo(iq)
        if action == "volumedefine":
            reply = self.iq_volumedefine(iq)
        if action == "volumedescription":
            reply = self.iq_volumedescription(iq)
        if action == "volumeundefine":
            reply = self.iq_volumeundefine(iq)
        if reply:
            conn.send(reply)
            raise xmpp.protocol.NodeProcessed

    def iq_volumeinfo(self, iq):
        """
        return information about a volume
        @type iq: xmpp.Protocol.Iq
        @param iq: the received IQ
        @rtype: xmpp.Protocol.Iq
        @return: a ready to send IQ containing the result of the action
        """
        try:
            reply = iq.buildReply("result")
            pool_identifier = iq.getTag("query").getTag("archipel").getAttr("pool")
            identifier = iq.getTag("query").getTag("archipel").getAttr("identifier")
            volumeInfo = self.volume_info(pool_identifier, identifier)
            infoNode = xmpp.Node("info", attrs=volumeInfo)
            reply.setQueryPayload([infoNode])
        except Exception as ex:
            reply = build_error_iq(self, ex, iq, ARCHIPEL_ERROR_CODE_STORAGE_VOLUME_INFO)
        return reply

    def iq_volumedefine(self, iq):
        """
        Define a new volume in a given pool
        @type iq: xmpp.Protocol.Iq
        @param iq: the received IQ
        @rtype: xmpp.Protocol.Iq
        @return: a ready to send IQ containing the result of the action
        """
        try:
            reply = iq.buildReply("result")
            pool_identifier = iq.getTag("query").getTag("archipel").getAttr("pool")
            xmldesc = iq.getTag("query").getTag("archipel").getTag("volume")
            volume = self.volume_define(pool_identifier, xmldesc)
            self.entity.shout("storagevolume", "I just defined a new volume named %s as asked by %s" % (volume.name(), iq.getFrom().getNode()))
        except Exception as ex:
            reply = build_error_iq(self, ex, iq, ARCHIPEL_ERROR_CODE_STORAGE_VOLUME_DEFINE)
        return reply

    def iq_volumeundefine(self, iq):
        """
        Undefine a volume from a given pool
        @type iq: xmpp.Protocol.Iq
        @param iq: the received IQ
        @rtype: xmpp.Protocol.Iq
        @return: a ready to send IQ containing the result of the action
        """
        try:
            reply = iq.buildReply("result")
            pool_identifier = iq.getTag("query").getTag("archipel").getAttr("pool")
            identifier = iq.getTag("query").getTag("archipel").getAttr("identifier")
            self.volume_undefine(pool_identifier, identifier)
            self.entity.shout("storagevolume", "I just undefined the volume named %s as asked by %s" % (identifier, iq.getFrom().getNode()))
        except Exception as ex:
            reply = build_error_iq(self, ex, iq, ARCHIPEL_ERROR_CODE_STORAGE_VOLUME_UNDEFINE)
        return reply

    def iq_volumedescription(self, iq):
        """
        Return the XML description of a volume
        @type iq: xmpp.Protocol.Iq
        @param iq: the received IQ
        @rtype: xmpp.Protocol.Iq
        @return: a ready to send IQ containing the result of the action
        """
        try:
            reply = iq.buildReply("result")
            pool_identifier = iq.getTag("query").getTag("archipel").getAttr("pool")
            identifier = iq.getTag("query").getTag("archipel").getAttr("identifier")
            description = self.volume_xmldesc(pool_identifier, identifier)
            reply.setQueryPayload([description])
        except Exception as ex:
            reply = build_error_iq(self, ex, iq, ARCHIPEL_ERROR_CODE_STORAGE_VOLUME_DESCRIPTION)
        return reply