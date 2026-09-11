-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 9.4.2                                       //
-- // Date : 2022-01-20                                     //
-- ///////////////////////////////////////////////////////////

UPDATE `${prefix}accessright` SET idAccessProfile=7 where idAccessProfile=8 and idMenu in (270,271) and idProfile=3;

UPDATE `${prefix}menu` SET idMenu=6, sortOrder=376 where id=270;
UPDATE `${prefix}menu` SET idMenu=6, sortOrder=377 where id=271;
UPDATE `${prefix}menu` SET level=NULL WHERE id in (232,233,235);
UPDATE `${prefix}menu` SET level='ReadWriteList' WHERE id=170;


INSERT INTO `${prefix}mailable` (name, `idle`) VALUES 
('IncomingMail', 0),
('OutgoingMail', 0);

INSERT INTO `${prefix}importable` (`name`, `idle`) VALUES
('IncomingMail',0),
('OutgoingMail',0);

INSERT INTO `${prefix}checklistable` (`name`, `idle`) VALUES 
('IncomingMail', 0),
('OutgoingMail',0);

INSERT INTO `${prefix}linkable` (`name`, `idle`) VALUES 
('IncomingMail', 0),
('OutgoingMail',0);

INSERT INTO `${prefix}originable` (`name`, `idle`) VALUES 
('IncomingMail', 0),
('OutgoingMail',0);

INSERT INTO `${prefix}textable` (`name`, `idle`) VALUES 
('IncomingMail', 0),
('OutgoingMail',0);

