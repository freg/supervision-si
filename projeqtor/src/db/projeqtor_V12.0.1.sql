-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 12.0.1                                      //
-- // Date : 2024-12-17                                     //
-- ///////////////////////////////////////////////////////////

INSERT INTO `${prefix}modulemenu` (`idModule`,`idMenu`,`hidden`,`active`) VALUES
(1,313,0,1),
(7,310,0,1),
(10,311,0,1),
(1,286,0,1),
(1,50,0,1);

-- Fix for reportList id : must be over 5000000 to avoid conflict with standard reports
UPDATE `${prefix}reportparameter` set idReport=idReport+5000000 where idReport<1000000 and idReport in (select id from `${prefix}report` where idReportCategory=21);
UPDATE `${prefix}reportparameter` set idReport=idReport+3000000 where idReport<5000000 and idReport>2000000 and idReport in (select id from `${prefix}report` where idReportCategory=21);
UPDATE `${prefix}habilitationreport` set idReport=idReport+5000000 where idReport<1000000 and idReport in (select id from `${prefix}report` where idReportCategory=21);
UPDATE `${prefix}habilitationreport` set idReport=idReport+3000000 where idReport<5000000 and idReport>2000000 and idReport in (select id from `${prefix}report` where idReportCategory=21);
UPDATE `${prefix}report` set id=id+5000000 where id<1000000 and idReportCategory=21;
UPDATE `${prefix}report` set id=id+3000000 where id<5000000 and id>2000000 and idReportCategory=21;
INSERT INTO `${prefix}report` (`id`, `name`, `idReportCategory`, `file`, `sortOrder`,`idle`) VALUES (5000000, 'startForReportList', 21, '', 0, 1);