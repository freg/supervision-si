-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 11.3.2                                      //
-- // Date : 2024-07-12                                     //
-- ///////////////////////////////////////////////////////////
-- Patch on V11.3

ALTER TABLE `${prefix}clientcontract` CHANGE `tokenLeft` `tokenLeft` decimal(5,2) DEFAULT NULL;
ALTER TABLE `${prefix}worktokenclientcontract` CHANGE `quantity` `quantity` decimal(7,2) unsigned DEFAULT NULL;

ALTER TABLE `${prefix}prospectorigin` CHANGE `sortOrder` `sortOrder`  int(5) unsigned DEFAULT NULL COMMENT '5';

UPDATE `${prefix}menu` set level='ReadWriteEnvironment' where name in ('menuProspect','menuProspectOrigin');
UPDATE `${prefix}menu` set level='ReadWriteList' where name in ('menuDomainProspect','menuPositionProspect','menuDecisionMakerProspect');
UPDATE `${prefix}menu` set idle=1, level=null where name in ('menuProspectEvent');

UPDATE `${prefix}accessright` set idAccessProfile=1000001 where idMenu in (301, 302, 303, 304, 305, 306, 307, 308) and idProfile=1;
UPDATE `${prefix}accessright` set idAccessProfile=1000002 where idMenu in (301, 302, 303, 304, 305, 306, 307, 308) and idProfile<>1;

UPDATE `${prefix}planningmode` SET mandatoryDuration=1 where id IN (27,28);