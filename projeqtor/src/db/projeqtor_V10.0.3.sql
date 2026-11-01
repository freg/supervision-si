-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 10.0.3                                      //
-- // Date : 2022-07-25                                     //
-- ///////////////////////////////////////////////////////////

-- Fix Skills Menus Skills

UPDATE `${prefix}menu` SET level='ReadWritePrincipal' WHERE id in (275,276) AND level is null; 

UPDATE `${prefix}accessright` SET idAccessProfile=1000001 WHERE idMenu in (275) AND idAccessProfile in (8, 7);
UPDATE `${prefix}accessright` SET idAccessProfile=1000001 WHERE idMenu in (276) AND idAccessProfile in (8,7) and idProfile=1;
UPDATE `${prefix}accessright` SET idAccessProfile=1000002 WHERE idMenu in (276) AND idAccessProfile in (8,7) and idProfile<>1;
DELETE FROM `${prefix}accessright` WHERE idMenu in (277,281);

-- Fix Voting Menus

UPDATE `${prefix}menu` SET level='ReadWritePrincipal' WHERE id in (278,279) AND level is null;
UPDATE `${prefix}menu` SET level='Project' WHERE id in (280) AND level is null;
UPDATE `${prefix}accessright` SET idAccessProfile=1000001 WHERE idMenu in (278,279) AND idAccessProfile in (8,7);
DELETE FROM `${prefix}accessright` WHERE idMenu in (282,283);