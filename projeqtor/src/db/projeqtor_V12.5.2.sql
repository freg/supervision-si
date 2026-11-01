-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 12.5.2                                      //
-- // Date : 2025-04-16                                     //
-- ///////////////////////////////////////////////////////////
-- Patch on V12.5

UPDATE `${prefix}menu` SET level='ReadWritePrincipal' where id in (320);
UPDATE `${prefix}accessright` set idAccessProfile=1000001 where idMenu in (320,322,328) and idProfile=1;
UPDATE `${prefix}accessright` set idAccessProfile=1000002 where idMenu in (320,322,328) and idProfile<>1;

CREATE INDEX workWorkdate ON `${prefix}work` (workDate);

ALTER TABLE `${prefix}tag` DROP INDEX tagName;
CREATE UNIQUE INDEX tagName ON `${prefix}tag` (`refType`,`name`, `idProject`);

UPDATE `${prefix}menu` SET idle=1, menuClass='Work' WHERE id=329;

UPDATE `${prefix}baseline` set idle=1 where idProject in (select id from `${prefix}project` WHERE idle=1);
