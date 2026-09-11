-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 12.1.2                                      //
-- // Date : 2025-05-06                                     //
-- ///////////////////////////////////////////////////////////

UPDATE `${prefix}report` set sortOrder=206 where id=146;
UPDATE `${prefix}report` set sortOrder=780 where id=145;

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`idReport`,`sortOrder`,`moduleName`) VALUES
(412, 'menuProspectEventType',398,308,0,921,'moduleCrmProspect');
